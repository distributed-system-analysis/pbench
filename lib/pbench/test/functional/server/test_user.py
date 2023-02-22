from http import HTTPStatus

import pytest
from requests import HTTPError

from pbench.client import API, PbenchServerClient

USERNAME1 = "tester"
USERNAME2 = "nonfunctional"
PASSWORD = "tests"


class TestUser:
    """
    Pbench Server functional tests for basic "user" operations.

    NOTE: The functional test system is intended to run on a pristine
    containerized Pbench Server. We could check for some pre-conditions if we
    had a known Administrative user (e.g., admin/admin).
    """

    @staticmethod
    def test_get_user_fail(server_client: PbenchServerClient, login_user):
        """Test get user on a non existent user"""
        with pytest.raises(
            HTTPError,
            match=f"FORBIDDEN for url: {server_client.scheme}://.*?/api/v1/user/{USERNAME2}",
        ):
            server_client.get_user(username=USERNAME2)

    @staticmethod
    def test_profile_noauth(server_client: PbenchServerClient):
        """Test that we can't access a user profile without authentication."""
        with pytest.raises(
            HTTPError,
            match=f"UNAUTHORIZED for url: {server_client.scheme}://.*?/api/v1/user/{USERNAME1}",
        ):
            server_client.get_user(username=USERNAME1, add_auth_header=False)

    @staticmethod
    def test_profile_bad_auth(server_client: PbenchServerClient):
        """Test that we can not access a user profile with an invalid
        authentication token.
        """
        with pytest.raises(
            HTTPError,
            match=f"UNAUTHORIZED for url: {server_client.scheme}://.*?/api/v1/user/{USERNAME1}",
        ):
            server_client.get(
                API.USER,
                {"target_username": USERNAME1},
                headers={"Authorization": "Bearer of bad tokens"},
            )

    @staticmethod
    def test_get_user_success(server_client: PbenchServerClient, login_user):
        """Test that we can access a user profile with a valid authentication
        token. And that all the user fields we imported in our internal db
        are correct.
        """
        response = server_client.get(API.USER, {"target_username": USERNAME1})
        assert response.status_code == HTTPStatus.OK
        response_json = response.json()
        oidc_user = server_client.oidc_admin.get_user(token=server_client.auth_token)
        assert response_json["username"] == USERNAME1
        assert response_json["first_name"] == oidc_user["given_name"] == "Test"
        assert response_json["last_name"] == oidc_user["family_name"] == "User"
        assert response_json["email"] == oidc_user["email"] == "tester@gmail.com"
