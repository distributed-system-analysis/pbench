from http import HTTPStatus
import os

import pytest

from pbench.client import PbenchServerClient
from pbench.client.oidc_admin import OIDCAdmin
from pbench.client.types import JSONOBJECT
from pbench.server.auth import OpenIDClientError

USER = {
    "username": "tester",
    "email": "tester@gmail.com",
    "password": "123456",
    "first_name": "Test",
    "last_name": "User",
}

ADMIN = {
    "username": "testadmin",
    "email": "testadmin@gmail.com",
    "password": "123456",
    "first_name": "Admin",
    "last_name": "Tester",
}


@pytest.fixture(scope="session")
def server_client():
    """
    Used by Pbench Server functional tests to connect to a server.

    If run without a PBENCH_SERVER environment variable pointing to the server
    instance, this will fail the test run.
    """
    host = os.environ.get("PBENCH_SERVER")
    assert (
        host
    ), "Pbench Server functional tests require that PBENCH_SERVER be set to the hostname of a server"
    client = PbenchServerClient(host)
    client.connect({"accept": "application/json"})
    assert client.endpoints
    return client


@pytest.fixture(scope="session")
def oidc_admin(server_client: PbenchServerClient):
    """
    Used by Pbench Server functional tests to get admin access
    on the test OIDC server.
    """
    return OIDCAdmin(server_url=server_client.endpoints["openid"]["server"])


def register_user(oidc_admin: OIDCAdmin, user: JSONOBJECT):
    try:
        response = oidc_admin.create_new_user(**user)
    except OpenIDClientError as e:
        # To allow testing outside our transient CI containers, allow the tester
        # user to already exist.
        if e.http_status != HTTPStatus.CONFLICT:
            raise e
        pass
    else:
        assert response.ok, f"Register failed with {response.json()}"


@pytest.fixture(scope="session")
def register_test_user(oidc_admin: OIDCAdmin):
    """Create a test user for functional tests."""
    register_user(oidc_admin, USER)


@pytest.fixture(scope="session")
def register_admintest_user(oidc_admin: OIDCAdmin):
    """Create a test user matching the configured Pbench admin."""
    register_user(oidc_admin, ADMIN)


@pytest.fixture
def login_user(server_client: PbenchServerClient, register_test_user):
    """Log in the test user and return the authentication token"""
    server_client.login(USER["username"], USER["password"])
    assert server_client.auth_token
    yield
    server_client.auth_token = None


@pytest.fixture
def login_admin(server_client: PbenchServerClient, register_admintest_user):
    """Log in the test user and return the authentication token"""
    server_client.login(ADMIN["username"], ADMIN["password"])
    assert server_client.auth_token
    yield
    server_client.auth_token = None
