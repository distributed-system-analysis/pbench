from http import HTTPStatus
import pytest
import requests
import responses


class TestLogin:
    def test_login(self, connect):
        """
        Confirm that a successful Pbench Server login captures the 'username'
        and 'auth_token' in the client object.
        """
        url = f"{connect.url}/api/v1/login"
        with responses.RequestsMock() as rsp:
            rsp.add(
                responses.POST, url, json={"username": "user", "auth_token": "foobar"}
            )
            connect.login("user", "password")
            assert len(rsp.calls) == 1
            assert rsp.calls[0].request.url == url
            assert rsp.calls[0].response.status_code == 200

            assert connect.username == "user"
            assert connect.auth_token == "foobar"

    def test_bad_login(self, connect):
        """
        Confirm that a failure from the Pbench Server login API is correctly
        handled by the client library, and does not set the client 'username`
        and 'auth_token' properties.
        """
        url = f"{connect.url}/api/v1/login"
        with responses.RequestsMock() as rsp:
            rsp.add(
                responses.POST,
                url,
                status=HTTPStatus.UNAUTHORIZED,
                json={"username": "user", "auth_token": "foobar"},
            )

            with pytest.raises(requests.HTTPError):
                connect.login("user", "password")

            assert len(rsp.calls) == 1
            assert rsp.calls[0].request.url == url
            assert rsp.calls[0].response.status_code == 401

            assert connect.username is None
            assert connect.auth_token is None
