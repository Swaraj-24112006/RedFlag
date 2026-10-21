import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role
from tests.factories import UserFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_password():
    return "password123"


@pytest.fixture
def test_user(db, user_password):
    return UserFactory(username="testoperator", password=user_password, role=Role.OPERATOR)


@pytest.fixture
def supervisor_user(db, user_password):
    return UserFactory(username="testsupervisor", password=user_password, role=Role.SUPERVISOR)


@pytest.fixture
def qa_custodian_user(db, user_password):
    return UserFactory(username="testqacustodian", password=user_password, role=Role.QA_CUSTODIAN)


@pytest.fixture
def admin_user(db, user_password):
    return UserFactory(username="testadmin", password=user_password, role=Role.ADMIN, is_staff=True, is_superuser=True)


@pytest.fixture
def auth_client(api_client):
    def _auth_client(user):
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return api_client
    return _auth_client
