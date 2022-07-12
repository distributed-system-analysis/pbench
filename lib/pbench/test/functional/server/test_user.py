from http import HTTPStatus

import pytest
from requests import HTTPError

from pbench.client import Pbench


class TestUser:
    """
    Pbench Server functional tests for basic "user" operations.

    NOTE: The functional test system is intended to run on a pristine
    containerized Pbench Server. We could check for some pre-conditions if we
    had a known Administrative user (e.g., admin/admin).
    """

    USERNAME = "functional"
    PASSWORD = "tests"

    def test_login_fail(self, pbench: Pbench):
        """
        Trying to log in to a non-existent user should fail.

        NOTE: This will fail if "nouser" exists.
        """
        with pytest.raises(HTTPError) as e:
            pbench.login("nouser", "nopassword")
        assert (
            str(e.value)
            == "401 Client Error: UNAUTHORIZED for url: http://10.1.170.201/api/v1/login"
        )

    def test_register(self, pbench: Pbench):
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
        response = pbench.post("register", json=json)
        assert response.status_code == HTTPStatus.CREATED

    def test_profile_noauth(self, pbench: Pbench):
        """
        Test that we can't access a user profile without authentication.
        """
        with pytest.raises(HTTPError) as e:
            pbench.get("user", {"target_username": self.USERNAME})
        assert (
            str(e.value)
            == "401 Client Error: UNAUTHORIZED for url: http://10.1.170.201/api/v1/user/functional"
        )

    def test_login(self, pbench: Pbench):
        """
        Test that we can log in using our new user.

        NOTE: This assumes test cases will be run in order. There are Pytest
        plugins to explicitly control test case order, but Pytest generally
        does run tests within a single class in order. Is it worth taking on
        another dependency to make this explicit?
        """
        pbench.login(self.USERNAME, self.PASSWORD)

    def test_profile(self, pbench: Pbench):
        """
        Test that we can retrieve our own user profile once logged in.

        NOTE: This assumes test cases will be run in order.
        """
        response = pbench.get("user", {"target_username": self.USERNAME})
        assert response.json()["username"] == self.USERNAME

    def test_update(self, pbench: Pbench):
        """
        Test that we can update our own user profile once logged in.

        NOTE: This assumes test cases will be run in order.
        """
        response = pbench.get("user", {"target_username": self.USERNAME})
        user = response.json()
        user["first_name"] = "Mycroft"

        # Remove fields that PUT will reject, but use a copy so that we can
        # compare the new value against what we expect.
        #
        # This is unfortunate: PUT should IGNORE unmodifiable fields to allow a
        # standard REST GET/update/PUT sequence.
        payload = user.copy()
        del payload["registered_on"]

        response = pbench.put("user", {"target_username": self.USERNAME}, json=payload)

        response = pbench.get("user", {"target_username": self.USERNAME})
        updated = response.json()
        assert user == updated

    def test_delete(self, pbench: Pbench):
        """
        Test that we can delete our own user profile once logged in.

        NOTE: This assumes test cases will be run in order.
        """
        pbench.delete("user", {"target_username": self.USERNAME})
