import csv
import os
import uuid
import logging
from io import BytesIO

from django.http import StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from PIL import Image
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.common.storage import (
    generate_presigned_post,
    get_file_bytes_dual,
    get_object_bytes,
    head_object,
    is_minio_available,
    put_object_bytes,
    save_file_dual,
)

logger = logging.getLogger(__name__)

from .models import (
    Attachment,
    AttachmentKind,
    AttachmentStatus,
)
from .selectors import (
    RedFlagFilter,
    get_base_flags_queryset,
    get_flags_summary,
)
from .serializers import (
    AttachmentPresignRequestSerializer,
    AttachmentSerializer,
    ContainmentUnverifySerializer,
    ContainmentUpdateSerializer,
    ContainmentVerifySerializer,
    FieldChangeSerializer,
    RedFlagCreateSerializer,
    RedFlagDetailSerializer,
    RedFlagDetailsUpdateSerializer,
    RedFlagListSerializer,
    StatusHistorySerializer,
)
from .services import (
    create_red_flag,
    unverify_containment,
    update_containment,
    update_flag_details,
    verify_containment,
)


class Echo:
    """An object that implements just the write method of the file-like interface for streaming CSV."""
    def write(self, value):
        return value


def sanitize_csv_cell(value) -> str:
    """Guards against CSV formula injection in spreadsheet applications like Microsoft Excel."""
    if value is None:
        return ""
    val_str = str(value).replace("\r", " ").replace("\n", " ")
    if val_str and val_str[0] in ("=", "+", "-", "@"):
        return f"'{val_str}"
    return val_str


# ----------------------------------------------------------------------
# Dual-Mode Attachment Flow (MinIO first preference, Local Media fallback)
# ----------------------------------------------------------------------

class AttachmentDirectUploadView(APIView):
    """
    POST /api/redflag/v1/attachments/upload/
    Accepts multipart/form-data upload with 'file' and 'kind'.
    - First preference: MinIO S3 object storage.
    - Graceful fallback: local disk storage (settings.MEDIA_ROOT) when MinIO is down.
    Generates ~400px thumbnail and returns uploaded attachment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        kind = request.data.get("kind", AttachmentKind.EVIDENCE_BEFORE)
        if kind not in AttachmentKind.values:
            kind = AttachmentKind.EVIDENCE_BEFORE

        year = timezone.now().year
        ext = os.path.splitext(file_obj.name)[1].lower() or ".jpg"
        object_key = f"redflag/{year}/{uuid.uuid4()}{ext}"
        content_type = file_obj.content_type or "image/jpeg"
        file_bytes = file_obj.read()
        file_size = len(file_bytes)

        # Generate thumbnail
        thumb_key = f"redflag/{year}/thumb_{uuid.uuid4()}.jpg"
        thumb_bytes = None
        try:
            img = Image.open(BytesIO(file_bytes))
            img.thumbnail((400, 400))
            thumb_io = BytesIO()
            img_format = "JPEG" if img.format not in ["PNG", "WEBP"] else img.format
            img.convert("RGB").save(thumb_io, format=img_format, quality=85)
            thumb_bytes = thumb_io.getvalue()
        except Exception as e:
            logger.warning(f"Failed to generate thumbnail: {e}")

        # Dual save (MinIO first, local fallback)
        save_res = save_file_dual(object_key, file_bytes, content_type)
        if thumb_bytes:
            save_file_dual(thumb_key, thumb_bytes, "image/jpeg")

        attachment = Attachment.objects.create(
            kind=kind,
            object_key=object_key,
            thumbnail_key=thumb_key if thumb_bytes else "",
            content_type=content_type,
            size=file_size,
            status=AttachmentStatus.UPLOADED,
            uploaded_by=request.user,
        )

        return Response(
            {
                "success": True,
                "storage": save_res.get("storage", "local"),
                "attachment": AttachmentSerializer(attachment).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AttachmentPresignView(APIView):
    """
    POST /api/redflag/v1/attachments/presign/
    Generates a secure presigned POST policy allowing direct browser-to-MinIO uploads.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AttachmentPresignRequestSerializer, responses={201: dict})
    def post(self, request):
        serializer = AttachmentPresignRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        year = timezone.now().year
        ext = os.path.splitext(data["filename"])[1].lower() or ".jpg"
        object_key = f"redflag/{year}/{uuid.uuid4()}{ext}"

        # Create PENDING record
        attachment = Attachment.objects.create(
            kind=data["kind"],
            object_key=object_key,
            content_type=data["content_type"],
            size=data["size"],
            status=AttachmentStatus.PENDING,
            uploaded_by=request.user,
        )

        minio_up = False
        try:
            presigned_post = generate_presigned_post(
                object_key=object_key,
                content_type=data["content_type"],
                max_size_bytes=data["size"] + 1024 * 1024,
            )
            minio_up = True
        except Exception as e:
            logger.info(f"MinIO presigned post unavailable: {e}")
            presigned_post = {"url": "", "fields": {}}

        return Response(
            {
                "attachment_id": attachment.id,
                "object_key": object_key,
                "minio_available": minio_up,
                "presigned_post": presigned_post,
                "direct_upload_url": "/api/redflag/v1/attachments/upload/",
            },
            status=status.HTTP_201_CREATED,
        )


class AttachmentConfirmView(APIView):
    """
    POST /api/redflag/v1/attachments/{id}/confirm/
    Verifies that the file was uploaded, sniffs image bytes, and generates a ~400px thumbnail.
    Works for both MinIO and local disk storage.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            attachment = Attachment.objects.get(id=pk, uploaded_by=request.user)
        except Attachment.DoesNotExist:
            return Response({"error": "Attachment not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        actual_size = attachment.size
        # Download bytes to verify and thumbnail (from MinIO or local)
        try:
            img_bytes = get_file_bytes_dual(attachment.object_key)
            actual_size = len(img_bytes)
            img = Image.open(BytesIO(img_bytes))
            img.verify()  # Sniff valid image format

            # Generate thumbnail
            img = Image.open(BytesIO(img_bytes))
            img.thumbnail((400, 400))
            thumb_io = BytesIO()
            img_format = "JPEG" if img.format not in ["PNG", "WEBP"] else img.format
            img.convert("RGB").save(thumb_io, format=img_format, quality=85)
            thumb_data = thumb_io.getvalue()

            # Upload thumbnail via dual save
            year = timezone.now().year
            thumb_key = f"redflag/{year}/thumb_{uuid.uuid4()}.jpg"
            save_file_dual(thumb_key, thumb_data, content_type="image/jpeg")

            attachment.size = actual_size
            attachment.thumbnail_key = thumb_key
            attachment.status = AttachmentStatus.UPLOADED
            attachment.save(update_fields=["size", "thumbnail_key", "status"])

            return Response(
                {
                    "success": True,
                    "attachment": AttachmentSerializer(attachment).data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.warning(f"Attachment confirm error: {e}")
            attachment.status = AttachmentStatus.FAILED
            attachment.save(update_fields=["status"])
            return Response(
                {"error": f"Invalid image or thumbnail processing failure: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ----------------------------------------------------------------------
# RedFlag ViewSet (Phases 2, 3, 4)
# ----------------------------------------------------------------------

class RedFlagViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_class = RedFlagFilter
    ordering = ["-raised_at", "-id"]
    ordering_fields = ["raised_at", "severity", "status", "rf_no", "created_at"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return get_base_flags_queryset()

    def get_serializer_class(self):
        if self.action == "create":
            return RedFlagCreateSerializer
        elif self.action == "list":
            return RedFlagListSerializer
        elif self.action in ["details", "update_details"]:
            return RedFlagDetailsUpdateSerializer
        elif self.action in ["containment", "update_containment"]:
            return ContainmentUpdateSerializer
        return RedFlagDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = RedFlagCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag = create_red_flag(request.user, serializer.validated_data)
        return Response(RedFlagDetailSerializer(flag).data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # Phase 3: Summary KPIs
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """
        GET /api/redflag/v1/flags/summary/
        Returns Master Tracker KPI summary metrics via a single optimized aggregate query.
        Pass ?scoped=true to scope KPIs to current filters; otherwise defaults to all flags.
        """
        is_scoped = request.query_params.get("scoped", "false").lower() == "true"
        filtered_qs = self.filter_queryset(self.get_queryset())
        summary_data = get_flags_summary(filtered_qs, is_scoped=is_scoped)
        return Response(summary_data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Phase 3: CSV Export
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="export\\.csv")
    def export_csv(self, request):
        """
        GET /api/redflag/v1/flags/export.csv
        Streams Master Tracker flags into an Excel-friendly CSV with all 22 standard columns.
        Includes UTF-8 BOM and formula injection protection.
        """
        filtered_qs = self.filter_queryset(self.get_queryset())

        headers = [
            "Sr No",
            "Red Flag No",
            "Raised Date",
            "Raised By",
            "Originating Dept",
            "Target Dept",
            "Target Person",
            "Plant Area",
            "Station",
            "Model",
            "Type",
            "5M Category",
            "Severity",
            "Description",
            "Quarantined WIP",
            "QA Custodian",
            "Status",
            "Sustenance Start",
            "M1 Audit",
            "M2 Audit",
            "M3 Audit",
            "Sustenance Achieved",
        ]

        def csv_rows():
            # UTF-8 BOM so Excel opens non-ASCII characters without encoding glitches
            yield "\ufeff"
            echo_buffer = Echo()
            writer = csv.writer(echo_buffer)

            yield writer.writerow(headers)

            for flag in filtered_qs.iterator(chunk_size=500):
                c = getattr(flag, "containment", None)
                row = [
                    sanitize_csv_cell(flag.id),
                    sanitize_csv_cell(flag.rf_no),
                    sanitize_csv_cell(flag.raised_at.strftime("%Y-%m-%d %H:%M") if flag.raised_at else ""),
                    sanitize_csv_cell(flag.raised_by_name),
                    sanitize_csv_cell(flag.raised_by_department.name if flag.raised_by_department else ""),
                    sanitize_csv_cell(flag.target_department.name if flag.target_department else ""),
                    sanitize_csv_cell(flag.target_person),
                    sanitize_csv_cell(f"{flag.plant.code} - {flag.line_name}"),
                    sanitize_csv_cell(flag.station_name),
                    sanitize_csv_cell(flag.model_name),
                    sanitize_csv_cell(flag.red_flag_type),
                    sanitize_csv_cell(flag.category_5m),
                    sanitize_csv_cell(flag.severity),
                    sanitize_csv_cell(flag.description),
                    sanitize_csv_cell(c.qty_quarantined if c else 0),
                    sanitize_csv_cell(flag.qa_custodian.full_name if flag.qa_custodian else "Unassigned"),
                    sanitize_csv_cell(flag.get_status_display()),
                    sanitize_csv_cell(flag.sustenance_start_date.strftime("%Y-%m-%d") if flag.sustenance_start_date else "-"),
                    sanitize_csv_cell("-"),  # M1 Audit (Phase 6)
                    sanitize_csv_cell("-"),  # M2 Audit (Phase 6)
                    sanitize_csv_cell("-"),  # M3 Audit (Phase 6)
                    sanitize_csv_cell("Yes" if flag.sustenance_achieved else "No"),
                ]
                yield writer.writerow(row)

        now_str = timezone.now().strftime("%Y-%m-%d")
        response = StreamingHttpResponse(csv_rows(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="SFC_RedFlags_Master_{now_str}.csv"'
        return response

    # ------------------------------------------------------------------
    # Phase 4 Tab 1: Anomaly Details Update
    # ------------------------------------------------------------------
    @action(detail=True, methods=["patch"], url_path="details")
    def details(self, request, pk=None):
        """
        PATCH /api/redflag/v1/flags/{id}/details/
        Updates Tab 1 Anomaly details with optimistic concurrency version check.
        """
        flag = self.get_object()
        serializer = RedFlagDetailsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_flag = update_flag_details(
            flag=flag,
            data=serializer.validated_data,
            user=request.user,
            client_version=serializer.validated_data["version"],
        )
        return Response(RedFlagDetailSerializer(updated_flag).data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Phase 4 Tab 2: Containment Update & Sign-off
    # ------------------------------------------------------------------
    @action(detail=True, methods=["patch"], url_path="containment")
    def containment(self, request, pk=None):
        """
        PATCH /api/redflag/v1/flags/{id}/containment/
        Updates Tab 2 Containment details with optimistic concurrency version check.
        """
        flag = self.get_object()
        serializer = ContainmentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        update_containment(
            flag=flag,
            data=serializer.validated_data,
            user=request.user,
            client_version=serializer.validated_data["version"],
        )
        flag.refresh_from_db()
        return Response(RedFlagDetailSerializer(flag).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="containment/verify")
    def verify_containment_action(self, request, pk=None):
        """
        POST /api/redflag/v1/flags/{id}/containment/verify/
        QA Inspector / Supervisor containment sign-off with server timestamp and user attribution.
        """
        flag = self.get_object()
        # Permission check: QA or Supervisor or Admin
        allowed_roles = [Role.QA_INSPECTOR, Role.QA_CUSTODIAN, Role.SUPERVISOR, Role.ADMIN]
        if not (request.user.is_superuser or request.user.role in allowed_roles):
            raise PermissionDenied("Only Quality Inspectors, Supervisors, or Admins can verify containment.")

        serializer = ContainmentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verify_containment(flag=flag, user=request.user, note=serializer.validated_data.get("note", ""))
        flag.refresh_from_db()
        return Response(RedFlagDetailSerializer(flag).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="containment/unverify")
    def unverify_containment_action(self, request, pk=None):
        """
        POST /api/redflag/v1/flags/{id}/containment/unverify/
        Admin / QA Custodian un-verification with audit trail.
        """
        flag = self.get_object()
        serializer = ContainmentUnverifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        unverify_containment(flag=flag, user=request.user, reason=serializer.validated_data["reason"])
        flag.refresh_from_db()
        return Response(RedFlagDetailSerializer(flag).data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Phase 4: History & Timeline Endpoint
    # ------------------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """
        GET /api/redflag/v1/flags/{id}/history/
        Returns merged chronological audit trail (StatusHistory and FieldChanges).
        """
        flag = self.get_object()
        status_history = StatusHistorySerializer(flag.status_history.all(), many=True).data
        field_changes = FieldChangeSerializer(flag.field_changes.all(), many=True).data

        timeline = []
        for sh in status_history:
            timeline.append({
                "type": "STATUS_CHANGE",
                "timestamp": sh["changed_at"],
                "actor": sh["changed_by_name"],
                "description": f"Status changed from {sh['from_status'] or 'None'} to {sh['to_status']}",
                "reason": sh["reason"],
            })

        for fc in field_changes:
            timeline.append({
                "type": "FIELD_CHANGE",
                "timestamp": fc["changed_at"],
                "actor": fc["changed_by_name"],
                "description": f"Changed '{fc['field_name']}' from '{fc['old_value']}' to '{fc['new_value']}'",
                "reason": "",
            })

        timeline.sort(key=lambda x: x["timestamp"], reverse=True)
        return Response(timeline, status=status.HTTP_200_OK)
