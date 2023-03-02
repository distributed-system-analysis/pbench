from http import HTTPStatus
import os

import pytest

from pbench.client import PbenchServerClient
from pbench.client.oidc_admin import OIDCAdmin

USERNAME: str = "tester"
EMAIL: str = "tester@gmail.com"
PASSWORD: str = "123456"
FIRST_NAME: str = "Test"
LAST_NAME: str = "User"


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
    on OIDC server.
    """
    return OIDCAdmin(server_url=server_client.endpoints["openid"]["server"])


@pytest.fixture(scope="session")
def register_test_user(oidc_admin: OIDCAdmin):
    """Create a test user for functional tests."""
    response = oidc_admin.create_new_user(
        username=USERNAME,
        email=EMAIL,
        password=PASSWORD,
        first_name=FIRST_NAME,
        last_name=LAST_NAME,
    )

    # To allow testing outside our transient CI containers, allow the tester
    # user to already exist.
    assert (
        response.ok or response.status_code == HTTPStatus.CONFLICT
    ), f"Register failed with {response.json()}"


@pytest.fixture
def login_user(server_client: PbenchServerClient, register_test_user):
    """Log in the test user and return the authentication token"""
    server_client.login(USERNAME, PASSWORD)
    assert server_client.auth_token
