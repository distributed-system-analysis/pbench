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
            match=f"NOT FOUND for url: {server_client.scheme}://.*?/api/v1/user/{USERNAME2}",
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
        assert (
            response_json["profile"]["user"]["email"]
            == oidc_user["email"]
            == "tester@gmail.com"
        )
        assert (
            response_json["profile"]["user"]["first_name"]
            == oidc_user["given_name"]
            == "Test"
        )
        assert (
            response_json["profile"]["user"]["last_name"]
            == oidc_user["family_name"]
            == "User"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "case, data",
        [
            (1, {"user.department": "Perf_Scale", "user.company.name": "Red Hat"}),
            (2, {"user": {"email": "new_tester@gmail.com"}}),
            (3, {"user": {"company": {"location": "Westford"}}}),
        ],
    )
    def test_profile_update(server_client: PbenchServerClient, login_user, case, data):
        """Test user can update their own profile fields under the acceptable
        profile keys.
        """
        before_update = server_client.get_user(username=USERNAME1)
        response = server_client.put(
            API.USER, {"target_username": USERNAME1}, json={"profile": data}
        )
        assert response.status_code == HTTPStatus.OK
        if case == 1:
            assert before_update["profile"]["user"].get("department") is None
            assert before_update["profile"]["user"].get("company") is None
            assert response.json()["profile"]["user"]["department"] == "Perf_Scale"
            assert response.json()["profile"]["user"]["company"]["name"] == "Red Hat"
        elif case == 2:
            assert before_update["profile"]["user"]["email"] == "tester@gmail.com"
            assert response.json()["profile"]["user"]["email"] == "new_tester@gmail.com"
        elif case == 3:
            assert before_update["profile"]["user"]["company"].get("location") is None
            assert (
                response.json()["profile"]["user"]["company"]["location"] == "Westford"
            )

    @staticmethod
    def test_bad_profile_key_update(server_client: PbenchServerClient, login_user):
        """Test user can not update profile keys that are not updatable."""
        with pytest.raises(
            HTTPError,
            match=f"BAD REQUEST for url: {server_client.scheme}://.*?/api/v1/user/{USERNAME1}",
        ):
            server_client.put(
                API.USER,
                {"target_username": USERNAME1},
                json={"profile": {"server.role": "ADMIN"}},
            )

    @staticmethod
    def test_bad_profile_update_input(server_client: PbenchServerClient, login_user):
        """Test server rejects the bad formatted profile keys.
        E.g. user.email is a value so assigning user.email.new_key should fail.
        """
        with pytest.raises(
            HTTPError,
            match=f"BAD REQUEST for url: {server_client.scheme}://.*?/api/v1/user/{USERNAME1}",
        ):
            server_client.put(
                API.USER,
                {"target_username": USERNAME1},
                json={
                    "profile": {"user.email": "value", "user.email.new_key": "value"}
                },
            )
