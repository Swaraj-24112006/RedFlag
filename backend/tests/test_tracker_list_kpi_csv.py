import pytest
from django.urls import reverse
from rest_framework import status

from apps.redflag.models import Containment, RedFlag, RedFlagStatus
from tests.factories import DepartmentFactory, PlantFactory


@pytest.fixture
def seeded_flags(db, test_user):
    dept_prod = DepartmentFactory(code="PROD_TRK", name="Production Track")
    dept_qa = DepartmentFactory(code="QA_TRK", name="Quality Track")
    plant1 = PlantFactory(code="MF1_TRK", name="MF1 Assembly Track")
    plant2 = PlantFactory(code="MF2_TRK", name="MF2 Machining Track")

    flags = []
    # Flag 1: OPEN, CRITICAL, MF1
    f1 = RedFlag.objects.create(
        rf_no="RF-2026-0001",
        raised_by=test_user,
        raised_by_name=test_user.full_name,
        raised_by_role=test_user.role,
        raised_by_department=dept_prod,
        target_department=dept_qa,
        target_person="Sunita QA",
        plant=plant1,
        line_name="Vacuum Line",
        station_name="ST-10",
        model_name="VP-100",
        severity="CRITICAL",
        category_5m="Method",
        description="Vacuum seal leak in chamber",
        status=RedFlagStatus.OPEN,
        qa_custodian_status="REVIEW_PENDING",
    )
    Containment.objects.create(red_flag=f1, qty_quarantined=0, status="PENDING")
    flags.append(f1)

    # Flag 2: CONTAINED, MAJOR, MF2
    f2 = RedFlag.objects.create(
        rf_no="RF-2026-0002",
        raised_by=test_user,
        raised_by_name=test_user.full_name,
        raised_by_role=test_user.role,
        raised_by_department=dept_prod,
        target_department=dept_prod,
        target_person="Rajesh Tooling",
        plant=plant2,
        line_name="Grinding Line",
        station_name="ST-02",
        model_name="PUMP-200",
        severity="MAJOR",
        category_5m="Machine",
        description="Sparks bypassing safety guard",
        status=RedFlagStatus.CONTAINED,
        qa_custodian_status="REVIEW_PENDING",
    )
    Containment.objects.create(red_flag=f2, qty_quarantined=15, action="Fitted acrylic guard", status="CONTAINED")
    flags.append(f2)

    # Flag 3: CLOSED, SUSTAINED
    f3 = RedFlag.objects.create(
        rf_no="RF-2026-0003",
        raised_by=test_user,
        raised_by_name=test_user.full_name,
        raised_by_role=test_user.role,
        raised_by_department=dept_prod,
        target_department=dept_qa,
        target_person="Vijay Quality",
        plant=plant1,
        line_name="Assembly Line 3",
        station_name="ST-05",
        model_name="EGR-300",
        severity="MINOR",
        category_5m="Material",
        description="=SUM(A1:B1) potential injection text",
        status=RedFlagStatus.CLOSED,
        sustenance_achieved=True,
        qa_custodian_status="CONTAINMENT_VERIFIED",
    )
    Containment.objects.create(red_flag=f3, qty_quarantined=5, status="VERIFIED")
    flags.append(f3)

    return flags


@pytest.mark.django_db
class TestMasterTrackerAndExport:
    def test_list_flags_pagination(self, auth_client, test_user, seeded_flags):
        client = auth_client(test_user)
        url = reverse("redflag:flags-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "count" in data
        assert data["count"] == 3
        assert len(data["results"]) == 3

    def test_filter_by_status(self, auth_client, test_user, seeded_flags):
        client = auth_client(test_user)
        url = reverse("redflag:flags-list")
        response = client.get(f"{url}?status=OPEN")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["rfNo"] == "RF-2026-0001"

    def test_filter_by_severity_and_plant(self, auth_client, test_user, seeded_flags):
        client = auth_client(test_user)
        url = reverse("redflag:flags-list")
        response = client.get(f"{url}?severity=CRITICAL&plant=MF1_TRK")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["rfNo"] == "RF-2026-0001"

    def test_search_icontains(self, auth_client, test_user, seeded_flags):
        client = auth_client(test_user)
        url = reverse("redflag:flags-list")
        # Search by target person
        response = client.get(f"{url}?search=Rajesh")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 1
        assert response.json()["results"][0]["rfNo"] == "RF-2026-0002"

        # Search by description
        response = client.get(f"{url}?search=chamber")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 1

    def test_summary_kpi_metrics(self, auth_client, test_user, seeded_flags):
        client = auth_client(test_user)
        url = reverse("redflag:flags-summary")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["totalRaised"] == 3
        assert data["openActionNeeded"] == 2  # 1 OPEN + 1 CONTAINED
        assert data["containedCount"] == 1
        assert data["closedSustained"] == 1
        assert data["qaCustodianBacklog"] == 2

    def test_csv_export_streaming(self, auth_client, test_user, seeded_flags):
        client = auth_client(test_user)
        url = reverse("redflag:flags-export-csv")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv; charset=utf-8"
        assert "attachment; filename=" in response["Content-Disposition"]

        content = b"".join(response.streaming_content).decode("utf-8")
        lines = content.strip().split("\r\n")
        assert len(lines) >= 4  # Header + 3 rows

        # Verify 22 columns in header
        headers = lines[0].lstrip("\ufeff").split(",")
        assert len(headers) == 22
        assert headers[0] == "Sr No"
        assert headers[1] == "Red Flag No"
        assert headers[21] == "Sustenance Achieved"

        # Verify formula injection protection: =SUM(...) becomes '=SUM(...)
        assert "'=SUM(A1:B1) potential injection text" in content
