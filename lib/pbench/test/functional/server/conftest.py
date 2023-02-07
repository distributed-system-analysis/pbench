from http import HTTPStatus
import os

import pytest

from pbench.client import PbenchServerClient
from pbench.client.oidc_admin import OIDCAdmin
from pbench.client.types import JSONMap


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
def oidc_admin(server_client: PbenchServerClient):
    """
    Used by Pbench Server functional tests to get admin access
    on OIDC server.
    """
    oidc_endpoints = server_client.endpoints["openid-connect"]
    oidc_server = OIDCAdmin(server_url=oidc_endpoints["issuer"])
    return oidc_server


@pytest.fixture(scope="module")
def register_test_user(oidc_admin: OIDCAdmin):
    """Create a test user for functional tests."""
    response = oidc_admin.create_new_user(
        username="tester",
        email="tester@gmail.com",
        password="123456",
        first_name="Test",
        last_name="User",
    )

    # To allow testing outside our transient CI containers, allow the tester
    # user to already exist.
    assert (
        response.ok or response.status_code == HTTPStatus.FORBIDDEN
    ), f"Register failed with {response.json()}"


@pytest.fixture
def login_user(
    server_client: PbenchServerClient, oidc_admin: OIDCAdmin, register_test_user
):
    """Log in the test user and return the authentication token"""
    oidc_endpoints = server_client.endpoints["openid-connect"]
    response = oidc_admin.user_login(
        client_id=oidc_endpoints["client"], username="tester", password="123456"
    )
    auth_token = response.json()["access_token"]
    assert auth_token
    json = {"username": "tester", "auth_token": auth_token}
    server_client.username = "tester"
    server_client.auth_token = auth_token
    yield JSONMap(json)
