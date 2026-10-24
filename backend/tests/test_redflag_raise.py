from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import Role
from apps.redflag.models import Attachment, AttachmentKind, AttachmentStatus, RedFlag, RedFlagStatus
from tests.factories import DepartmentFactory, PlantFactory, UserFactory


@pytest.fixture
def sample_plant(db):
    return PlantFactory(code="MF1", name="MF1 Assembly")


@pytest.fixture
def sample_dept(db):
    return DepartmentFactory(code="PROD", name="Production")


@pytest.fixture
def target_dept(db):
    return DepartmentFactory(code="QA", name="Quality")


@pytest.fixture
def uploaded_before_attachment(db, test_user):
    return Attachment.objects.create(
        kind=AttachmentKind.EVIDENCE_BEFORE,
        object_key="redflag/2026/test_before.jpg",
        content_type="image/jpeg",
        size=10240,
        status=AttachmentStatus.UPLOADED,
        uploaded_by=test_user,
    )


@pytest.fixture
def uploaded_after_attachment(db, test_user):
    return Attachment.objects.create(
        kind=AttachmentKind.CONTAINMENT_AFTER,
        object_key="redflag/2026/test_after.jpg",
        content_type="image/jpeg",
        size=12000,
        status=AttachmentStatus.UPLOADED,
        uploaded_by=test_user,
    )


@pytest.mark.django_db
class TestRedFlagRaiseFlow:
    @patch("apps.redflag.views.generate_presigned_post", return_value={"url": "http://minio:9000", "fields": {}})
    def test_attachment_presign(self, mock_presign, auth_client, test_user):
        client = auth_client(test_user)
        url = reverse("redflag:attachment-presign")
        payload = {
            "kind": AttachmentKind.EVIDENCE_BEFORE,
            "filename": "sample_photo.jpg",
            "content_type": "image/jpeg",
            "size": 500000,
        }
        response = client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "attachmentId" in data or "attachment_id" in data
        assert "objectKey" in data or "object_key" in data
        assert "presignedPost" in data or "presigned_post" in data

    def test_create_red_flag_success(
        self, auth_client, test_user, target_dept, sample_plant, uploaded_before_attachment
    ):
        client = auth_client(test_user)
        url = reverse("redflag:flags-list")
        payload = {
            "target_department_id": target_dept.id,
            "target_person": "Amit Kumar",
            "team_leader": "Sanjay Patil",
            "line_name": "Assembly Line 1",
            "station_name": "ST-04 Torquing",
            "model_name": "Vacuum Pump V2",
            "plant_id": sample_plant.id,
            "red_flag_type": "Quality",
            "severity": "CRITICAL",
            "category_5m": "Method",
            "description": "Loose bolts observed on cylinder flange during shift start.",
            "qty_quarantined": 25,
            "containment_action": "Quarantined batch in quarantine area; tagged with red tag.",
            "evidence_before_id": uploaded_before_attachment.id,
        }

        response = client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        rf_num = data.get("rfNo") or data.get("rf_no")
        assert rf_num is not None
        assert rf_num.startswith("RF-")
        assert data["status"] == RedFlagStatus.CONTAINED  # Because quantity > 0
        target_p = data.get("targetPerson") or data.get("target_person")
        assert target_p == "Amit Kumar"

        # Verify DB records
        flag = RedFlag.objects.get(id=data["id"])
        assert flag.containment.qty_quarantined == 25
        assert flag.status_history.count() >= 1
        uploaded_before_attachment.refresh_from_db()
        assert uploaded_before_attachment.red_flag == flag

    def test_create_red_flag_quantity_zero_gives_open_status(
        self, auth_client, test_user, target_dept, sample_plant, uploaded_before_attachment
    ):
        client = auth_client(test_user)
        url = reverse("redflag:flags-list")
        payload = {
            "target_department_id": target_dept.id,
            "target_person": "Sunita Rao",
            "line_name": "Line 2",
            "station_name": "ST-01",
            "model_name": "EGR-50",
            "plant_id": sample_plant.id,
            "description": "No immediate containment yet.",
            "qty_quarantined": 0,
            "containment_action": "",
            "evidence_before_id": uploaded_before_attachment.id,
        }
        response = client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == RedFlagStatus.OPEN

    def test_missing_before_photo_returns_400(self, auth_client, test_user, target_dept, sample_plant):
        client = auth_client(test_user)
        url = reverse("redflag:flags-list")
        payload = {
            "target_department_id": target_dept.id,
            "target_person": "Amit Kumar",
            "line_name": "Line 1",
            "station_name": "ST-01",
            "model_name": "VP-1",
            "description": "Testing missing photo",
        }
        response = client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_use_another_users_attachment(
        self, auth_client, test_user, target_dept, sample_plant
    ):
        other_user = UserFactory(username="other_operator", role=Role.OPERATOR)
        other_attachment = Attachment.objects.create(
            kind=AttachmentKind.EVIDENCE_BEFORE,
            object_key="redflag/2026/other.jpg",
            content_type="image/jpeg",
            size=1024,
            status=AttachmentStatus.UPLOADED,
            uploaded_by=other_user,
        )

        client = auth_client(test_user)
        url = reverse("redflag:flags-list")
        payload = {
            "target_department_id": target_dept.id,
            "target_person": "Amit Kumar",
            "line_name": "Line 1",
            "station_name": "ST-01",
            "model_name": "VP-1",
            "description": "Attempting to hijack photo",
            "evidence_before_id": other_attachment.id,
        }
        response = client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
