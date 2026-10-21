import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestAuthentication:
    def test_token_obtain_pair_success(self, api_client, test_user, user_password):
        url = reverse("accounts:token_obtain_pair")
        payload = {
            "username": test_user.username,
            "password": user_password,
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert "user" in data
        assert data["user"]["username"] == test_user.username
        assert data["user"]["role"] == test_user.role

    def test_token_obtain_pair_invalid_credentials(self, api_client, test_user):
        url = reverse("accounts:token_obtain_pair")
        payload = {
            "username": test_user.username,
            "password": "wrongpassword",
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh_success(self, api_client, test_user, user_password):
        obtain_url = reverse("accounts:token_obtain_pair")
        resp = api_client.post(obtain_url, {"username": test_user.username, "password": user_password}, format="json")
        refresh_token = resp.json()["refresh"]

        refresh_url = reverse("accounts:token_refresh")
        response = api_client.post(refresh_url, {"refresh": refresh_token}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.json()

    def test_auth_me_authenticated(self, auth_client, test_user):
        client = auth_client(test_user)
        url = reverse("accounts:me")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == test_user.username
        assert data["role"] == test_user.role
        assert data["employeeId"] == test_user.employee_id
        assert data["department"]["id"] == test_user.department.id

    def test_auth_me_unauthenticated(self, api_client):
        url = reverse("accounts:me")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
