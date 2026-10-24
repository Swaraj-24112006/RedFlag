from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.redflag.models import (
    Containment,
    ContainmentStatus,
    FieldChange,
    RedFlag,
    RedFlagStatus,
)
from tests.factories import DepartmentFactory, PlantFactory


@pytest.fixture
def active_flag(db, test_user):
    dept = DepartmentFactory(code="DEPT_ACT", name="Active Dept")
    plant = PlantFactory(code="MF_ACT", name="Active Plant")

    flag = RedFlag.objects.create(
        rf_no="RF-2026-0099",
        version=1,
        raised_by=test_user,
        raised_by_name=test_user.full_name,
        raised_by_role=test_user.role,
        raised_by_department=dept,
        target_department=dept,
        target_person="Original Target",
        plant=plant,
        line_name="Line A",
        station_name="Station 1",
        model_name="Model X",
        severity="MAJOR",
        category_5m="Method",
        description="Original anomaly description",
        status=RedFlagStatus.OPEN,
        qa_custodian_status="REVIEW_PENDING",
    )
    Containment.objects.create(
        red_flag=flag,
        qty_quarantined=0,
        action="",
        status=ContainmentStatus.PENDING,
    )
    return flag


@pytest.mark.django_db
class TestActionModalAndContainment:
    def test_tab1_details_update_with_version_and_audit(self, auth_client, test_user, active_flag):
        client = auth_client(test_user)
        url = reverse("redflag:flags-details", kwargs={"pk": active_flag.id})

        payload = {
            "version": 1,
            "target_person": "Updated Target Person",
            "severity": "CRITICAL",
            "description": "Updated defect description with more details",
        }

        response = client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["version"] == 2
        assert data["targetPerson"] == "Updated Target Person"
        assert data["severity"] == "CRITICAL"

        # Check FieldChange audit rows
        changes = FieldChange.objects.filter(red_flag=active_flag)
        assert changes.count() >= 3
        field_names = [c.field_name for c in changes]
        assert "target_person" in field_names
        assert "severity" in field_names
        assert "description" in field_names

    def test_optimistic_concurrency_conflict_409(self, auth_client, test_user, active_flag):
        client = auth_client(test_user)
        url = reverse("redflag:flags-details", kwargs={"pk": active_flag.id})

        # Client sends stale version (e.g. 99 instead of 1)
        payload = {
            "version": 99,
            "target_person": "Will Fail",
        }
        response = client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_tab2_containment_update(self, auth_client, test_user, active_flag):
        client = auth_client(test_user)
        url = reverse("redflag:flags-containment", kwargs={"pk": active_flag.id})

        payload = {
            "version": 1,
            "qty_quarantined": 50,
            "containment_action": "Moved to quarantine pallet with Red Tag RT-2026-104",
            "red_tag_no": "RT-2026-104",
        }
        response = client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["containment"]["qtyQuarantined"] == 50
        assert data["containment"]["redTagNo"] == "RT-2026-104"
        assert data["status"] == RedFlagStatus.CONTAINED
        assert data["containment"]["status"] == ContainmentStatus.CONTAINED

    def test_containment_verification_and_backlog_drop(
        self, auth_client, qa_custodian_user, active_flag
    ):
        # Setup containment first
        active_flag.containment.qty_quarantined = 20
        active_flag.containment.action = "Isolated lot"
        active_flag.containment.save()

        client = auth_client(qa_custodian_user)
        url = reverse("redflag:flags-verify-containment-action", kwargs={"pk": active_flag.id})

        response = client.post(url, {"note": "Verified lot segregation and tag validity."}, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["containment"]["status"] == ContainmentStatus.VERIFIED
        assert data["containment"]["verifiedByName"] == qa_custodian_user.full_name
        assert data["qaCustodianStatus"] == "CONTAINMENT_VERIFIED"

        # Verify idempotency
        resp2 = client.post(url, {"note": "Verifying again"}, format="json")
        assert resp2.status_code == status.HTTP_200_OK

    def test_containment_sla_calculation(self, auth_client, test_user, active_flag):
        # Flag raised 130 minutes ago, not yet contained -> Breached
        past_time = timezone.now() - timedelta(minutes=130)
        RedFlag.objects.filter(id=active_flag.id).update(raised_at=past_time)

        client = auth_client(test_user)
        url = reverse("redflag:flags-detail", kwargs={"pk": active_flag.id})
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["containmentSlaBreached"] is True

    def test_history_timeline_endpoint(self, auth_client, test_user, active_flag):
        # Make a change to create a FieldChange
        client = auth_client(test_user)
        url_details = reverse("redflag:flags-details", kwargs={"pk": active_flag.id})
        client.patch(url_details, {"version": 1, "description": "Timeline test change"}, format="json")

        url_hist = reverse("redflag:flags-history", kwargs={"pk": active_flag.id})
        response = client.get(url_hist)
        assert response.status_code == status.HTTP_200_OK
        timeline = response.json()
        assert len(timeline) >= 1
        types = [t["type"] for t in timeline]
        assert "FIELD_CHANGE" in types
