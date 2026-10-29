from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from .views import (
    AttachmentConfirmView,
    AttachmentDirectUploadView,
    AttachmentPresignView,
    RedFlagViewSet,
)

app_name = "redflag"

router = DefaultRouter()
router.register(r"flags", RedFlagViewSet, basename="flags")

urlpatterns = [
    # Attachment flow (Dual-mode: direct multipart upload & S3 presign)
    path("attachments/upload/", AttachmentDirectUploadView.as_view(), name="attachment-upload"),
    path("attachments/presign/", AttachmentPresignView.as_view(), name="attachment-presign"),
    path("attachments/<int:pk>/confirm/", AttachmentConfirmView.as_view(), name="attachment-confirm"),

    # Direct CSV export route match
    re_path(r"^flags/export\.csv$", RedFlagViewSet.as_view({"get": "export_csv"}), name="flags-export-csv"),

    # RedFlag ViewSet routes
    path("", include(router.urls)),
]
