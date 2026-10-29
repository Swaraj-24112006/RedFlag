from rest_framework import serializers

from apps.common.storage import (
    generate_presigned_get,
    get_file_url,
)

from .models import (
    Attachment,
    AttachmentKind,
    AttachmentStatus,
    Containment,
    FieldChange,
    RedFlag,
    StatusHistory,
)
from .selectors import calculate_containment_sla

# ----------------------------------------------------------------------
# Attachment Serializers
# ----------------------------------------------------------------------

class AttachmentPresignRequestSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=AttachmentKind.choices)
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    size = serializers.IntegerField(min_value=1, max_value=15 * 1024 * 1024)

    def validate_content_type(self, value):
        allowed = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
        if value.lower() not in allowed:
            raise serializers.ValidationError(f"Content type '{value}' is not allowed. Supported: JPEG, PNG, WebP.")
        return value.lower()


class AttachmentConfirmSerializer(serializers.Serializer):
    attachment_id = serializers.IntegerField()


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True, default="")

    class Meta:
        model = Attachment
        fields = [
            "id",
            "kind",
            "object_key",
            "thumbnail_key",
            "content_type",
            "size",
            "status",
            "is_current",
            "url",
            "thumbnail_url",
            "uploaded_by_name",
            "created_at",
        ]

    def get_url(self, obj):
        if obj.status == AttachmentStatus.UPLOADED and obj.object_key:
            return get_file_url(obj.object_key)
        return None

    def get_thumbnail_url(self, obj):
        key = obj.thumbnail_key or obj.object_key
        if obj.status == AttachmentStatus.UPLOADED and key:
            return get_file_url(key)
        return None
        return None


# ----------------------------------------------------------------------
# Containment & History Serializers
# ----------------------------------------------------------------------

class ContainmentSerializer(serializers.ModelSerializer):
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True, allow_null=True)

    class Meta:
        model = Containment
        fields = [
            "id",
            "status",
            "qty_quarantined",
            "action",
            "red_tag_no",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "contained_at",
            "verification_note",
        ]


class StatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True, allow_null=True)

    class Meta:
        model = StatusHistory
        fields = [
            "id",
            "from_status",
            "to_status",
            "changed_by_name",
            "changed_at",
            "reason",
        ]


class FieldChangeSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True, allow_null=True)

    class Meta:
        model = FieldChange
        fields = [
            "id",
            "field_name",
            "old_value",
            "new_value",
            "changed_by_name",
            "changed_at",
        ]


# ----------------------------------------------------------------------
# RedFlag List & Detail Serializers
# ----------------------------------------------------------------------

class RedFlagListSerializer(serializers.ModelSerializer):
    sr_no = serializers.IntegerField(source="id", read_only=True)
    raised_by_department_code = serializers.CharField(source="raised_by_department.code", read_only=True)
    raised_by_department_name = serializers.CharField(source="raised_by_department.name", read_only=True)
    target_department_code = serializers.CharField(source="target_department.code", read_only=True)
    target_department_name = serializers.CharField(source="target_department.name", read_only=True)
    plant_code = serializers.CharField(source="plant.code", read_only=True)
    qa_custodian_name = serializers.CharField(source="qa_custodian.full_name", read_only=True, allow_null=True)

    containment_action = serializers.SerializerMethodField()
    qty_quarantined = serializers.SerializerMethodField()
    containment_status = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    containment_sla_minutes = serializers.SerializerMethodField()
    containment_sla_breached = serializers.SerializerMethodField()

    class Meta:
        model = RedFlag
        fields = [
            "id",
            "sr_no",
            "version",
            "rf_no",
            "raised_at",
            "target_date",
            "raised_by_name",
            "raised_by_role",
            "raised_by_department_code",
            "raised_by_department_name",
            "target_department_code",
            "target_department_name",
            "target_person",
            "team_leader",
            "closure_responsibility",
            "plant_code",
            "line_name",
            "station_name",
            "model_name",
            "red_flag_type",
            "red_flag_subtype",
            "category_5m",
            "severity",
            "description",
            "containment_action",
            "qty_quarantined",
            "containment_status",
            "status",
            "qa_custodian_name",
            "qa_custodian_status",
            "sustenance_start_date",
            "sustenance_achieved",
            "thumbnail_url",
            "containment_sla_minutes",
            "containment_sla_breached",
        ]

    def get_containment_action(self, obj):
        c = getattr(obj, "containment", None)
        return c.action if c else ""

    def get_qty_quarantined(self, obj):
        c = getattr(obj, "containment", None)
        return c.qty_quarantined if c else 0

    def get_containment_status(self, obj):
        c = getattr(obj, "containment", None)
        return c.status if c else "PENDING"

    def get_thumbnail_url(self, obj):
        # Prefetched current evidence
        ev_list = getattr(obj, "current_evidence", None)
        if ev_list and len(ev_list) > 0:
            att = ev_list[0]
            key = att.thumbnail_key or att.object_key
            return get_file_url(key)
        return None

    def get_containment_sla_minutes(self, obj):
        return calculate_containment_sla(obj)["containment_sla_minutes"]

    def get_containment_sla_breached(self, obj):
        return calculate_containment_sla(obj)["containment_sla_breached"]


class RedFlagDetailSerializer(serializers.ModelSerializer):
    sr_no = serializers.IntegerField(source="id", read_only=True)
    raised_by_department_code = serializers.CharField(source="raised_by_department.code", read_only=True)
    raised_by_department_name = serializers.CharField(source="raised_by_department.name", read_only=True)
    target_department_code = serializers.CharField(source="target_department.code", read_only=True)
    target_department_name = serializers.CharField(source="target_department.name", read_only=True)
    plant_code = serializers.CharField(source="plant.code", read_only=True)
    qa_custodian_name = serializers.CharField(source="qa_custodian.full_name", read_only=True, allow_null=True)

    containment = ContainmentSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    status_history = StatusHistorySerializer(many=True, read_only=True)
    field_changes = FieldChangeSerializer(many=True, read_only=True)

    containment_sla_minutes = serializers.SerializerMethodField()
    containment_sla_breached = serializers.SerializerMethodField()

    class Meta:
        model = RedFlag
        fields = [
            "id",
            "sr_no",
            "version",
            "rf_no",
            "raised_at",
            "target_date",
            "raised_by_name",
            "raised_by_role",
            "raised_by_department_code",
            "raised_by_department_name",
            "target_department_id",
            "target_department_code",
            "target_department_name",
            "target_person",
            "team_leader",
            "closure_responsibility",
            "qa_custodian_id",
            "qa_custodian_name",
            "qa_custodian_status",
            "qa_custodian_notes",
            "plant_id",
            "plant_code",
            "line_name",
            "station_name",
            "model_name",
            "red_flag_type",
            "red_flag_subtype",
            "category_5m",
            "severity",
            "repetitive_occurrence",
            "description",
            "status",
            "sustenance_start_date",
            "sustenance_achieved",
            "containment",
            "attachments",
            "status_history",
            "field_changes",
            "containment_sla_minutes",
            "containment_sla_breached",
            "created_at",
            "updated_at",
        ]

    def get_containment_sla_minutes(self, obj):
        return calculate_containment_sla(obj)["containment_sla_minutes"]

    def get_containment_sla_breached(self, obj):
        return calculate_containment_sla(obj)["containment_sla_breached"]


# ----------------------------------------------------------------------
# Mutation & Update Serializers
# ----------------------------------------------------------------------

class RedFlagCreateSerializer(serializers.Serializer):
    target_department_id = serializers.IntegerField(required=False)
    target_department = serializers.CharField(required=False)
    target_person = serializers.CharField(max_length=150)
    team_leader = serializers.CharField(max_length=150, required=False, allow_blank=True)
    line_name = serializers.CharField(max_length=150)
    station_name = serializers.CharField(max_length=150)
    model_name = serializers.CharField(max_length=150)
    plant_id = serializers.IntegerField(required=False)
    plant = serializers.CharField(required=False)
    red_flag_type = serializers.CharField(max_length=50, default="Quality")
    red_flag_subtype = serializers.CharField(max_length=100, required=False, allow_blank=True)
    severity = serializers.CharField(max_length=50, default="MAJOR")
    category_5m = serializers.CharField(max_length=50, default="Method")
    repetitive_occurrence = serializers.BooleanField(default=False)
    description = serializers.CharField()
    qty_quarantined = serializers.IntegerField(default=0, min_value=0)
    suspect_qty_quarantined = serializers.IntegerField(required=False, default=0, min_value=0)
    containment_action = serializers.CharField(required=False, allow_blank=True)
    red_tag_no = serializers.CharField(max_length=50, required=False, allow_blank=True)
    evidence_before_id = serializers.IntegerField()
    containment_after_id = serializers.IntegerField(required=False, allow_null=True)
    target_date = serializers.DateField(required=False)


class RedFlagDetailsUpdateSerializer(serializers.Serializer):
    """Phase 4 Tab 1 (Anomaly Details) PATCH serializer."""
    version = serializers.IntegerField(help_text="Expected version for optimistic locking")
    target_department_id = serializers.IntegerField(required=False)
    target_department = serializers.CharField(required=False)
    target_person = serializers.CharField(max_length=150, required=False)
    team_leader = serializers.CharField(max_length=150, required=False, allow_blank=True)
    closure_responsibility = serializers.CharField(max_length=150, required=False, allow_blank=True)
    qa_custodian_id = serializers.IntegerField(required=False, allow_null=True)
    qa_custodian_notes = serializers.CharField(required=False, allow_blank=True)
    red_flag_type = serializers.CharField(max_length=50, required=False)
    red_flag_subtype = serializers.CharField(max_length=100, required=False, allow_blank=True)
    category_5m = serializers.CharField(max_length=50, required=False)
    severity = serializers.CharField(max_length=50, required=False)
    description = serializers.CharField(required=False)
    target_date = serializers.DateField(required=False)
    evidence_before_id = serializers.IntegerField(required=False)


class ContainmentUpdateSerializer(serializers.Serializer):
    """Phase 4 Tab 2 (Containment) PATCH serializer."""
    version = serializers.IntegerField(help_text="Expected version for optimistic locking")
    qty_quarantined = serializers.IntegerField(required=False, min_value=0)
    suspect_qty_quarantined = serializers.IntegerField(required=False, min_value=0)
    action = serializers.CharField(required=False, allow_blank=True)
    containment_action = serializers.CharField(required=False, allow_blank=True)
    red_tag_no = serializers.CharField(max_length=50, required=False, allow_blank=True)


class ContainmentVerifySerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ContainmentUnverifySerializer(serializers.Serializer):
    reason = serializers.CharField(required=True)
