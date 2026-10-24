from django.conf import settings
from django.db import models

from apps.masterdata.models import Department, Line, Plant, Station


class AttachmentKind(models.TextChoices):
    EVIDENCE_BEFORE = "EVIDENCE_BEFORE", "Evidence (Before)"
    CONTAINMENT_AFTER = "CONTAINMENT_AFTER", "Containment (After)"
    CLOSURE = "CLOSURE", "Closure Evidence"


class AttachmentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Upload"
    UPLOADED = "UPLOADED", "Uploaded & Verified"
    FAILED = "FAILED", "Upload Failed"


class RedFlagStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CONTAINED = "CONTAINED", "Contained"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    UNDER_SUSTENANCE = "UNDER_SUSTENANCE", "Under Sustenance"
    CLOSED = "CLOSED", "Closed"
    REJECTED = "REJECTED", "Rejected"


class ContainmentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Containment"
    CONTAINED = "CONTAINED", "Contained"
    VERIFIED = "VERIFIED", "Verified"


class QaCustodianStatus(models.TextChoices):
    REVIEW_PENDING = "REVIEW_PENDING", "Review Pending"
    CONTAINMENT_VERIFIED = "CONTAINMENT_VERIFIED", "Containment Verified"
    CLOSURE_APPROVED = "CLOSURE_APPROVED", "Closure Approved"


class RedFlagCounter(models.Model):
    """Atomic sequence counter per calendar year for unique RF numbers (e.g. RF-2026-0001)."""
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Year {self.year}: Last #{self.last_number}"


class RedFlag(models.Model):
    # Optimistic Concurrency Control (Phase 4)
    version = models.PositiveIntegerField(default=1, help_text="Monotonically increasing version for optimistic locking")

    # Identity
    rf_no = models.CharField(max_length=50, unique=True, db_index=True, help_text="e.g. RF-2026-0001")

    # Timing
    raised_at = models.DateTimeField(auto_now_add=True, db_index=True)
    target_date = models.DateField(null=True, blank=True)

    # People & Roles
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="raised_flags",
    )
    raised_by_name = models.CharField(max_length=150)
    raised_by_role = models.CharField(max_length=50)
    raised_by_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="originating_flags",
    )
    target_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="targeted_flags",
        db_index=True,
    )
    target_person = models.CharField(max_length=150)
    team_leader = models.CharField(max_length=150, blank=True, default="")
    closure_responsibility = models.CharField(max_length=150, blank=True, default="")

    qa_custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_flags",
    )
    qa_custodian_status = models.CharField(max_length=50, default="REVIEW_PENDING")
    qa_custodian_notes = models.TextField(blank=True, default="")

    # Location & Production Context
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="red_flags")
    line_name = models.CharField(max_length=150)
    station_name = models.CharField(max_length=150)
    model_name = models.CharField(max_length=150)
    line = models.ForeignKey(Line, on_delete=models.SET_NULL, null=True, blank=True)
    station = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, blank=True)

    # Classification
    red_flag_type = models.CharField(max_length=50, default="Quality")
    red_flag_subtype = models.CharField(max_length=100, blank=True, default="")
    severity = models.CharField(max_length=50, db_index=True, default="MAJOR")
    category_5m = models.CharField(max_length=50, default="Method")
    repetitive_occurrence = models.BooleanField(default=False)
    description = models.TextField()

    # Sustenance & Closure State (Phases 3, 4, 6)
    sustenance_start_date = models.DateField(null=True, blank=True)
    sustenance_achieved = models.BooleanField(default=False)

    # Lifecycle State
    status = models.CharField(
        max_length=50,
        choices=RedFlagStatus.choices,
        default=RedFlagStatus.OPEN,
        db_index=True,
    )
    is_void = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-raised_at"]
        indexes = [
            models.Index(fields=["status", "-raised_at"]),
            models.Index(fields=["target_department", "status"]),
            models.Index(fields=["severity"]),
        ]

    def __str__(self):
        return f"{self.rf_no} - {self.description[:40]}"


class Containment(models.Model):
    red_flag = models.OneToOneField(RedFlag, on_delete=models.CASCADE, related_name="containment")
    status = models.CharField(
        max_length=50,
        choices=ContainmentStatus.choices,
        default=ContainmentStatus.PENDING,
    )
    qty_quarantined = models.PositiveIntegerField(default=0)
    action = models.TextField(blank=True, default="")
    red_tag_no = models.CharField(max_length=50, blank=True, default="")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_containments",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    contained_at = models.DateTimeField(null=True, blank=True)
    verification_note = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(qty_quarantined__gte=0),
                name="qty_quarantined_non_negative",
            )
        ]

    def __str__(self):
        return f"Containment for {self.red_flag.rf_no} (Qty: {self.qty_quarantined}, Status: {self.status})"


class Attachment(models.Model):
    kind = models.CharField(max_length=50, choices=AttachmentKind.choices)
    red_flag = models.ForeignKey(
        RedFlag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attachments",
    )
    object_key = models.CharField(max_length=500)
    thumbnail_key = models.CharField(max_length=500, blank=True, default="")
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    status = models.CharField(
        max_length=50,
        choices=AttachmentStatus.choices,
        default=AttachmentStatus.PENDING,
    )
    is_current = models.BooleanField(
        default=True,
        help_text="True if this is the active evidence attachment. Superseded attachments remain is_current=False for audit.",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.kind}: {self.object_key} ({self.status})"


class StatusHistory(models.Model):
    red_flag = models.ForeignKey(RedFlag, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=50)
    to_status = models.CharField(max_length=50)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flag_status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["changed_at"]

    def __str__(self):
        return f"{self.red_flag.rf_no}: {self.from_status} -> {self.to_status}"


class FieldChange(models.Model):
    """Field-level audit trail for IATF 16949 compliance (Phase 4)."""
    red_flag = models.ForeignKey(RedFlag, on_delete=models.CASCADE, related_name="field_changes")
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_field_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.red_flag.rf_no} {self.field_name}: '{self.old_value}' -> '{self.new_value}'"
