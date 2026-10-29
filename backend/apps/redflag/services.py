from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.accounts.models import Role, User
from apps.masterdata.models import Department, Plant

from .models import (
    Attachment,
    AttachmentKind,
    AttachmentStatus,
    Containment,
    ContainmentStatus,
    FieldChange,
    RedFlag,
    RedFlagCounter,
    RedFlagStatus,
    StatusHistory,
)


class ConcurrencyConflictError(APIException):
    status_code = 409
    default_detail = "Conflict: This record has been modified by another user. Please reload."
    default_code = "conflict"


ALLOWED_TRANSITIONS = {
    RedFlagStatus.OPEN: [RedFlagStatus.CONTAINED],
    RedFlagStatus.CONTAINED: [RedFlagStatus.OPEN, RedFlagStatus.IN_PROGRESS],
    RedFlagStatus.IN_PROGRESS: [RedFlagStatus.UNDER_SUSTENANCE],
    RedFlagStatus.UNDER_SUSTENANCE: [RedFlagStatus.CLOSED],
}


def next_rf_no() -> str:
    """
    Atomically generates the next unique sequential Red Flag number for the current calendar year.
    Thread-safe and multi-process safe using SELECT FOR UPDATE.
    Format: RF-{year}-{counter:04d} (e.g. RF-2026-0001).
    """
    current_year = timezone.now().year
    with transaction.atomic():
        counter, _ = RedFlagCounter.objects.select_for_update().get_or_create(year=current_year)
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        return f"RF-{current_year}-{counter.last_number:04d}"


def record_field_changes(flag: RedFlag, changes: dict, user: User):
    """
    Audits changes made to a RedFlag or its Containment for IATF compliance.
    changes: dict of {field_name: (old_value, new_value)}
    """
    for field_name, (old_val, new_val) in changes.items():
        old_str = "" if old_val is None else str(old_val)
        new_str = "" if new_val is None else str(new_val)
        if old_str != new_str:
            FieldChange.objects.create(
                red_flag=flag,
                field_name=field_name,
                old_value=old_str,
                new_value=new_str,
                changed_by=user,
            )


def transition(flag: RedFlag, to_status: str, user: User, reason: str = "") -> RedFlag:
    """
    Executes a formal lifecycle transition on a RedFlag.
    Enforces the state machine rules and records audit history in StatusHistory.
    """
    from_status = flag.status
    if from_status == to_status:
        return flag

    # Validate against allowed transitions
    allowed = ALLOWED_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        # Special case: Admin reversion from CONTAINED to OPEN
        if from_status == RedFlagStatus.CONTAINED and to_status == RedFlagStatus.OPEN:
            if not (user.is_superuser or user.role == Role.ADMIN):
                raise PermissionDenied("Only an Administrator can revert a contained flag to Open.")
            if not reason:
                raise ValidationError("A reason is mandatory when reverting a flag to Open.")
        else:
            raise ValidationError(
                f"Cannot transition flag from '{from_status}' to '{to_status}'. Allowed transitions: {allowed}"
            )

    flag.status = to_status
    flag.save(update_fields=["status", "updated_at"])

    StatusHistory.objects.create(
        red_flag=flag,
        from_status=from_status,
        to_status=to_status,
        changed_by=user,
        reason=reason,
    )
    return flag


def create_red_flag(user: User, data: dict) -> RedFlag:
    """
    Executes the complete Phase 2 Red Flag creation flow inside a single atomic transaction.
    Server sets identity, originator snapshot, containment status, and links verified photos.
    """
    description = (data.get("description") or "").strip()
    if not description:
        raise ValidationError({"description": "Description cannot be blank."})

    target_person = (data.get("target_person") or "").strip()
    line_name = (data.get("line_name") or "").strip()
    station_name = (data.get("station_name") or "").strip()
    model_name = (data.get("model_name") or "").strip()

    if not all([target_person, line_name, station_name, model_name]):
        raise ValidationError(
            {"target_person": "Target person, line, station, and model are required fields."}
        )

    # Validate target department
    target_dept_val = data.get("target_department_id") or data.get("target_department")
    target_dept = None
    if isinstance(target_dept_val, Department):
        target_dept = target_dept_val
    elif target_dept_val:
        target_dept = (
            Department.objects.filter(code__iexact=str(target_dept_val)).first()
            or Department.objects.filter(name__iexact=str(target_dept_val)).first()
        )
        if not target_dept:
            try:
                target_dept = Department.objects.filter(id=int(target_dept_val)).first()
            except (ValueError, TypeError):
                pass
    if not target_dept:
        target_dept = Department.objects.filter(is_active=True).first() or Department.objects.first()

    # Validate Originator Department from request user
    originating_dept = getattr(user, "department", None)
    if not originating_dept:
        originating_dept = target_dept

    # Validate Plant
    plant_val = data.get("plant_id") or data.get("plant")
    plant = None
    if isinstance(plant_val, Plant):
        plant = plant_val
    elif plant_val:
        plant = (
            Plant.objects.filter(code__iexact=str(plant_val)).first()
            or Plant.objects.filter(name__iexact=str(plant_val)).first()
        )
        if not plant:
            try:
                plant = Plant.objects.filter(id=int(plant_val)).first()
            except (ValueError, TypeError):
                pass
    if not plant:
        plant = Plant.objects.filter(is_active=True).first() or Plant.objects.first()

    # Validate evidence before attachment
    evidence_before_id = data.get("evidence_before_id")
    if not evidence_before_id:
        raise ValidationError({"evidence_before_id": "Before photo evidence is required."})

    try:
        evidence_attachment = Attachment.objects.get(
            id=evidence_before_id,
            kind=AttachmentKind.EVIDENCE_BEFORE,
            status=AttachmentStatus.UPLOADED,
            uploaded_by=user,
            red_flag__isnull=True,
        )
    except Attachment.DoesNotExist:
        raise ValidationError(
            {"evidence_before_id": "Uploaded before photo evidence not found, unconfirmed, or already linked."}
        )

    # Optional containment after attachment
    containment_after_id = data.get("containment_after_id")
    containment_attachment = None
    if containment_after_id:
        try:
            containment_attachment = Attachment.objects.get(
                id=containment_after_id,
                kind=AttachmentKind.CONTAINMENT_AFTER,
                status=AttachmentStatus.UPLOADED,
                uploaded_by=user,
                red_flag__isnull=True,
            )
        except Attachment.DoesNotExist:
            raise ValidationError(
                {"containment_after_id": "Uploaded after photo evidence not found, unconfirmed, or already linked."}
            )

    # Assign default QA custodian (setting or first active QA_CUSTODIAN user)
    qa_custodian = None
    custodian_id = data.get("qa_custodian_id") or data.get("qa_custodian")
    if custodian_id:
        qa_custodian = User.objects.filter(id=custodian_id, role__in=[Role.QA_CUSTODIAN, Role.QA_INSPECTOR]).first()
    if not qa_custodian:
        qa_custodian = User.objects.filter(role=Role.QA_CUSTODIAN, is_active=True).first()

    # Timing
    now = timezone.now()
    target_date = data.get("target_date") or (now + timedelta(days=5)).date()

    with transaction.atomic():
        rf_no = next_rf_no()

        flag = RedFlag.objects.create(
            rf_no=rf_no,
            target_date=target_date,
            raised_by=user,
            raised_by_name=user.full_name,
            raised_by_role=user.role,
            raised_by_department=originating_dept,
            target_department=target_dept,
            target_person=target_person,
            team_leader=data.get("team_leader", ""),
            closure_responsibility=data.get("closure_responsibility", ""),
            qa_custodian=qa_custodian,
            qa_custodian_status="REVIEW_PENDING",
            plant=plant,
            line_name=line_name,
            station_name=station_name,
            model_name=model_name,
            line_id=data.get("line_id"),
            station_id=data.get("station_id"),
            red_flag_type=data.get("red_flag_type", "Quality"),
            red_flag_subtype=data.get("red_flag_subtype", ""),
            severity=data.get("severity", "MAJOR"),
            category_5m=data.get("category_5m", "Method"),
            repetitive_occurrence=bool(data.get("repetitive_occurrence", False)),
            description=description,
            status=RedFlagStatus.OPEN,
            version=1,
        )

        # Containment logic
        qty_quarantined = int(data.get("qty_quarantined") or data.get("suspect_qty_quarantined") or 0)
        containment_action = (data.get("containment_action") or "").strip()
        red_tag_no = (data.get("red_tag_no") or "").strip()

        is_contained = qty_quarantined > 0 or bool(containment_action)
        containment_status = ContainmentStatus.CONTAINED if is_contained else ContainmentStatus.PENDING

        Containment.objects.create(
            red_flag=flag,
            status=containment_status,
            qty_quarantined=qty_quarantined,
            action=containment_action,
            red_tag_no=red_tag_no,
            contained_at=now if is_contained else None,
        )

        # Link attachments
        evidence_attachment.red_flag = flag
        evidence_attachment.is_current = True
        evidence_attachment.save(update_fields=["red_flag", "is_current"])

        if containment_attachment:
            containment_attachment.red_flag = flag
            containment_attachment.is_current = True
            containment_attachment.save(update_fields=["red_flag", "is_current"])

        # Determine initial status
        initial_status = RedFlagStatus.CONTAINED if is_contained else RedFlagStatus.OPEN
        flag.status = initial_status
        flag.save(update_fields=["status"])

        StatusHistory.objects.create(
            red_flag=flag,
            from_status="",
            to_status=initial_status,
            changed_by=user,
            reason="Red Flag initially raised on shop floor",
        )

    return flag


def update_flag_details(flag: RedFlag, data: dict, user: User, client_version: int) -> RedFlag:
    """
    Phase 4 Tab 1 (Anomaly Details) PATCH endpoint service.
    Implements optimistic concurrency control (version lock) and field-level audit.
    """
    if flag.status == RedFlagStatus.CLOSED:
        raise PermissionDenied("Closed Red Flags cannot be modified.")

    if flag.version != client_version:
        raise ConcurrencyConflictError(
            f"Conflict: Flag was updated by another user (Current server version: {flag.version}, submitted: {client_version})."
        )

    changes = {}

    # Target Department
    target_dept_id = data.get("target_department_id") or data.get("target_department")
    if target_dept_id:
        target_dept = Department.objects.get(id=target_dept_id)
        if target_dept != flag.target_department:
            changes["target_department"] = (flag.target_department.name, target_dept.name)
            flag.target_department = target_dept

    # Standard mutable strings
    for field in ["target_person", "team_leader", "closure_responsibility", "red_flag_type", "red_flag_subtype", "category_5m", "severity", "description"]:
        if field in data and data[field] is not None:
            new_val = str(data[field]).strip()
            old_val = getattr(flag, field)
            if new_val != old_val:
                changes[field] = (old_val, new_val)
                setattr(flag, field, new_val)

    if "target_date" in data and data["target_date"]:
        new_target = data["target_date"]
        if str(new_target) != str(flag.target_date):
            changes["target_date"] = (flag.target_date, new_target)
            flag.target_date = new_target

    if "qa_custodian_notes" in data:
        new_notes = str(data["qa_custodian_notes"]).strip()
        if new_notes != flag.qa_custodian_notes:
            changes["qa_custodian_notes"] = (flag.qa_custodian_notes, new_notes)
            flag.qa_custodian_notes = new_notes

    # Custodian Change
    custodian_id = data.get("qa_custodian_id") or data.get("qa_custodian")
    if custodian_id and custodian_id != (flag.qa_custodian_id if flag.qa_custodian else None):
        new_custodian = User.objects.filter(id=custodian_id).first()
        if not new_custodian or new_custodian.role not in [Role.QA_CUSTODIAN, Role.QA_INSPECTOR, Role.ADMIN]:
            raise ValidationError({"qa_custodian": "New custodian must have a Quality or Admin role."})
        changes["qa_custodian"] = (flag.qa_custodian.username if flag.qa_custodian else "None", new_custodian.username)
        flag.qa_custodian = new_custodian
        flag.qa_custodian_status = "REVIEW_PENDING"

    # Photo replacement
    new_evidence_id = data.get("evidence_before_id")
    if new_evidence_id:
        new_att = Attachment.objects.filter(id=new_evidence_id, kind=AttachmentKind.EVIDENCE_BEFORE, status=AttachmentStatus.UPLOADED).first()
        if new_att and new_att.red_flag_id != flag.id:
            # Mark previous before attachments as superseded (is_current=False)
            flag.attachments.filter(kind=AttachmentKind.EVIDENCE_BEFORE).update(is_current=False)
            new_att.red_flag = flag
            new_att.is_current = True
            new_att.save(update_fields=["red_flag", "is_current"])
            changes["evidence_before"] = ("Previous Photo", new_att.object_key)

    with transaction.atomic():
        flag.version += 1
        flag.save()
        record_field_changes(flag, changes, user)

    return flag


def update_containment(flag: RedFlag, data: dict, user: User, client_version: int) -> Containment:
    """
    Phase 4 Tab 2 (Containment Details) PATCH endpoint service.
    Updates quarantined quantity, action description, and red tag number.
    """
    if flag.status == RedFlagStatus.CLOSED:
        raise PermissionDenied("Closed Red Flags cannot be modified.")

    if flag.version != client_version:
        raise ConcurrencyConflictError(
            f"Conflict: Flag was updated by another user (Server version: {flag.version}, submitted: {client_version})."
        )

    containment = getattr(flag, "containment", None)
    if not containment:
        containment = Containment.objects.create(red_flag=flag)

    changes = {}
    now = timezone.now()

    if "qty_quarantined" in data or "suspect_qty_quarantined" in data:
        new_qty = int(data.get("qty_quarantined") or data.get("suspect_qty_quarantined") or 0)
        if new_qty != containment.qty_quarantined:
            changes["containment_qty_quarantined"] = (containment.qty_quarantined, new_qty)
            containment.qty_quarantined = new_qty

    if "action" in data or "containment_action" in data:
        new_act = (data.get("action") or data.get("containment_action") or "").strip()
        if new_act != containment.action:
            changes["containment_action"] = (containment.action, new_act)
            containment.action = new_act

    if "red_tag_no" in data:
        new_tag = (data.get("red_tag_no") or "").strip()
        if new_tag != containment.red_tag_no:
            changes["red_tag_no"] = (containment.red_tag_no, new_tag)
            containment.red_tag_no = new_tag

    # SLA and state transition trigger
    if (containment.qty_quarantined > 0 or containment.action) and not containment.contained_at:
        containment.contained_at = now
        containment.status = ContainmentStatus.CONTAINED
        if flag.status == RedFlagStatus.OPEN:
            flag.status = RedFlagStatus.CONTAINED
            flag.save(update_fields=["status"])
            StatusHistory.objects.create(
                red_flag=flag,
                from_status=RedFlagStatus.OPEN,
                to_status=RedFlagStatus.CONTAINED,
                changed_by=user,
                reason="Containment action/quantity recorded",
            )

    with transaction.atomic():
        flag.version += 1
        flag.save(update_fields=["version", "updated_at"])
        containment.save()
        record_field_changes(flag, changes, user)

    return containment


def verify_containment(flag: RedFlag, user: User, note: str = "") -> Containment:
    """
    Phase 4 Tab 2 Containment Sign-Off: POST /api/redflag/v1/flags/{id}/containment/verify/
    Requires QA or Supervisor role. Idempotent. Sets verified_by, verified_at, and transitions status.
    """
    containment = getattr(flag, "containment", None)
    if not containment:
        raise ValidationError("Containment record not found for this flag.")

    if not (containment.qty_quarantined > 0 or containment.action):
        raise ValidationError("Cannot verify empty containment. Quarantine quantity or containment action must be recorded.")

    # Idempotent return if already verified
    if containment.status == ContainmentStatus.VERIFIED and containment.verified_by:
        return containment

    now = timezone.now()
    changes = {
        "containment_status": (containment.status, ContainmentStatus.VERIFIED),
        "containment_verified_by": (containment.verified_by.username if containment.verified_by else "None", user.username),
    }

    with transaction.atomic():
        containment.status = ContainmentStatus.VERIFIED
        containment.verified_by = user
        containment.verified_at = now
        containment.verification_note = note
        containment.save()

        # Update QA Custodian review state to remove from backlog
        flag.qa_custodian_status = "CONTAINMENT_VERIFIED"
        if flag.status == RedFlagStatus.OPEN:
            flag.status = RedFlagStatus.CONTAINED
        flag.version += 1
        flag.save(update_fields=["qa_custodian_status", "status", "version", "updated_at"])

        record_field_changes(flag, changes, user)

    return containment


def unverify_containment(flag: RedFlag, user: User, reason: str) -> Containment:
    """
    Phase 4 Tab 2 Admin / QA Custodian un-verification: POST /flags/{id}/containment/unverify/
    """
    if not (user.is_superuser or user.role in [Role.QA_CUSTODIAN, Role.ADMIN]):
        raise PermissionDenied("Only an Administrator or QA Custodian can un-verify containment.")

    if not reason.strip():
        raise ValidationError("A reason is required to un-verify containment.")

    containment = getattr(flag, "containment", None)
    if not containment:
        raise ValidationError("Containment record not found.")

    with transaction.atomic():
        old_verifier = containment.verified_by.username if containment.verified_by else "None"
        containment.status = ContainmentStatus.CONTAINED
        containment.verified_by = None
        containment.verified_at = None
        containment.save()

        flag.qa_custodian_status = "REVIEW_PENDING"
        flag.version += 1
        flag.save(update_fields=["qa_custodian_status", "version", "updated_at"])

        FieldChange.objects.create(
            red_flag=flag,
            field_name="containment_verified",
            old_value=f"Verified by {old_verifier}",
            new_value="Unverified",
            changed_by=user,
        )

    return containment
