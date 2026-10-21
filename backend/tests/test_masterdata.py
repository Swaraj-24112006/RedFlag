import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import Role, User
from apps.masterdata.models import Department, Line, Plant, Station
from tests.factories import DepartmentFactory, LineFactory, PlantFactory, StationFactory


@pytest.mark.django_db
class TestMasterdata:
    def test_list_departments(self, auth_client, test_user):
        DepartmentFactory(code="PROD_TEST", name="Production Test")
        DepartmentFactory(code="QA_TEST", name="Quality Test")

        client = auth_client(test_user)
        url = reverse("masterdata:department-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 2

    def test_list_plants(self, auth_client, test_user):
        PlantFactory(code="MF1_TEST", name="MF1 Assembly")
        PlantFactory(code="MF2_TEST", name="MF2 Machining")

        client = auth_client(test_user)
        url = reverse("masterdata:plant-list")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 2

    def test_filter_lines_by_plant(self, auth_client, test_user):
        plant1 = PlantFactory(code="P1")
        plant2 = PlantFactory(code="P2")

        line1 = LineFactory(plant=plant1, code="L1")
        line2 = LineFactory(plant=plant2, code="L2")

        client = auth_client(test_user)
        url = reverse("masterdata:line-list")
        response = client.get(f"{url}?plant={plant1.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        line_ids = [item["id"] for item in data]
        assert line1.id in line_ids
        assert line2.id not in line_ids

    def test_filter_stations_by_line(self, auth_client, test_user):
        line1 = LineFactory(code="LN1")
        line2 = LineFactory(code="LN2")

        station1 = StationFactory(line=line1, code="ST1")
        station2 = StationFactory(line=line2, code="ST2")

        client = auth_client(test_user)
        url = reverse("masterdata:station-list")
        response = client.get(f"{url}?line={line1.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        station_ids = [item["id"] for item in data]
        assert station1.id in station_ids
        assert station2.id not in station_ids

    def test_seed_masterdata_command(self):
        call_command("seed_masterdata")
        assert Department.objects.filter(code="PROD").exists()
        assert Department.objects.filter(code="SUPP", is_internal=False).exists()
        assert Plant.objects.filter(code="MF1").exists()
        assert Line.objects.filter(code="MF1-L1").exists()
        assert Station.objects.count() > 0

    def test_seed_demo_users_command(self):
        call_command("seed_masterdata")
        call_command("seed_demo_users")

        roles = [
            Role.OPERATOR,
            Role.SUPERVISOR,
            Role.DEPT_LEAD,
            Role.QA_INSPECTOR,
            Role.QA_CUSTODIAN,
            Role.PLANT_HEAD,
            Role.ADMIN,
        ]
        for role in roles:
            assert User.objects.filter(role=role).exists(), f"Missing seeded user for role {role}"

        # Verify QA Custodian specifically
        custodian = User.objects.filter(role=Role.QA_CUSTODIAN).first()
        assert custodian is not None
        assert custodian.department.code == "QA"
