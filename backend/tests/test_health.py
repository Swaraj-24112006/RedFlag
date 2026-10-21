from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestHealthAndDocs:
    @patch("apps.common.health.check_minio_health", return_value=True)
    def test_health_endpoint_healthy(self, mock_minio, api_client):
        url = reverse("health")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["database"]["status"] == "up"
        assert data["services"]["minio"]["status"] == "up"

    @patch("apps.common.health.check_minio_health", return_value=False)
    def test_health_endpoint_degraded(self, mock_minio, api_client):
        url = reverse("health")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["minio"]["status"] == "down"

    def test_openapi_schema(self, api_client):
        url = reverse("schema")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_swagger_ui(self, api_client):
        url = reverse("swagger-ui")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert b"swagger-ui" in response.content.lower()
