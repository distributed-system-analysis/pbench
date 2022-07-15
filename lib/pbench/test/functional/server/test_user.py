from http import HTTPStatus

import pytest
from requests import HTTPError

from pbench.client import PbenchServerClient


class TestUser:
    """
    Pbench Server functional tests for basic "user" operations.

    NOTE: The functional test system is intended to run on a pristine
    containerized Pbench Server. We could check for some pre-conditions if we
    had a known Administrative user (e.g., admin/admin).
    """

    USERNAME = "functional"
    PASSWORD = "tests"

    def test_login_fail(self, pbench_server_client: PbenchServerClient):
        """
        Trying to log in to a non-existent user should fail.

        NOTE: This will fail if "nouser" exists.
        """
        with pytest.raises(HTTPError, match=r"UNAUTHORIZED for url: http://.*?/api/v1/login"):
            pbench_server_client.login("nouser", "nopassword")

    def test_register(self, pbench_server_client: PbenchServerClient):
        """
        Test that we can register a new user.

        NOTE: This will fail if the username already exists.
        """
        json = {
            "username": self.USERNAME,
            "first_name": "Test",
            "last_name": "Account",
            "password": self.PASSWORD,
            "email": f"{self.USERNAME}@example.com",
        }
        response = pbench_server_client.post("register", json=json)
        assert response.status_code == HTTPStatus.CREATED

    def test_register_redux(self, pbench_server_client: PbenchServerClient):
        """
        Test that an attempt to register an existing user fails.
        """
        json = {
            "username": self.USERNAME,
            "first_name": "Repeat",
            "last_name": "Redux",
            "password": self.PASSWORD,
            "email": f"{self.USERNAME}@example.com",
        }
        with pytest.raises(HTTPError, match=r"FORBIDDEN for url: http://.*?/api/v1/register"):
            pbench_server_client.post("register", json=json)

    def test_profile_noauth(self, pbench_server_client: PbenchServerClient):
        """
        Test that we can't access a user profile without authentication.
        """
        with pytest.raises(HTTPError, match=r"UNAUTHORIZED for url: http://.*?/api/v1/user/functional"):
            pbench_server_client.get("user", {"target_username": self.USERNAME})

    def test_login(self, pbench_server_client: PbenchServerClient):
        """
        Test that we can log in using our new user.

        NOTE: This assumes test cases will be run in order. There are Pytest
        plugins to explicitly control test case order, but Pytest generally
        does run tests within a single class in order. Is it worth taking on
        another dependency to make this explicit?
        """
        pbench_server_client.login(self.USERNAME, self.PASSWORD)
        assert pbench_server_client.auth_token

    def test_profile(self, pbench_server_client: PbenchServerClient):
        """
        Test that we can retrieve our own user profile once logged in.

        NOTE: This assumes test cases will be run in order.
        """
        response = pbench_server_client.get("user", {"target_username": self.USERNAME})
        assert response.json()["username"] == self.USERNAME

    def test_update(self, pbench_server_client: PbenchServerClient):
        """
        Test that we can update our own user profile once logged in.

        NOTE: This assumes test cases will be run in order.
        """
        response = pbench_server_client.get("user", {"target_username": self.USERNAME})
        user = response.json()
        assert user["first_name"] != "Mycroft"
        user["first_name"] = "Mycroft"

        # Remove fields that PUT will reject, but use a copy so that we can
        # compare the new value against what we expect.
        #
        # This is unfortunate: PUT should IGNORE unmodifiable fields to allow a
        # standard REST GET/update/PUT sequence.
        payload = user.copy()
        del payload["registered_on"]

        response = pbench_server_client.put("user", {"target_username": self.USERNAME}, json=payload)
        put_response = response.json()

        response = pbench_server_client.get("user", {"target_username": self.USERNAME})
        updated = response.json()
        assert user == updated
        assert put_response == user

    def test_delete(self, pbench_server_client: PbenchServerClient):
        """
        Test that we can delete our own user profile once logged in.

        NOTE: This assumes test cases will be run in order.
        """
        pbench_server_client.delete("user", {"target_username": self.USERNAME})
