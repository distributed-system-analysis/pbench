from http import HTTPStatus
import os

import pytest

from pbench.client import API, PbenchServerClient


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


@pytest.fixture
def register_test_user(server_client: PbenchServerClient):
    """Create a test user for functional tests."""

    response = server_client.post(
        API.REGISTER,
        json={
            "username": "tester",
            "first_name": "Test",
            "last_name": "User",
            "password": "123456",
            "email": "tester@gmail.com",
        },
        raise_error=False,
    )

    # To allow testing outside our transient CI containers, allow the tester
    # user to already exist.
    assert (
        response.ok or response.status_code == HTTPStatus.FORBIDDEN
    ), f"Register failed with {response.json()}"


@pytest.fixture
def login_user(server_client, register_test_user):
    """Log in the test user and return the authentication token"""
    server_client.login("tester", "123456")
    assert server_client.auth_token
