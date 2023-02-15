from http import HTTPStatus

import responses


class TestLogin:
    def test_login(self, connect):
        """
        Confirm that a successful Pbench Server login captures the 'username'
        and 'auth_token' in the client object.
        """
        oidc_server = connect.endpoints["openid"]["server"]
        oidc_realm = connect.endpoints["openid"]["realm"]
        url = f"{oidc_server}/realms/{oidc_realm}/protocol/openid-connect/token"
        with responses.RequestsMock() as rsp:
            rsp.add(responses.POST, url, json={"access_token": "foobar"})
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
        oidc_server = connect.endpoints["openid"]["server"]
        oidc_realm = connect.endpoints["openid"]["realm"]
        url = f"{oidc_server}/realms/{oidc_realm}/protocol/openid-connect/token"
        with responses.RequestsMock() as rsp:
            rsp.add(
                responses.POST,
                url,
                status=HTTPStatus.UNAUTHORIZED,
                json={"error_description": "Invalid user credentials"},
            )
            connect.login("user", "password")
            assert len(rsp.calls) == 1
            assert rsp.calls[0].request.url == url
            assert rsp.calls[0].response.status_code == 401

            assert connect.username is None
            assert connect.auth_token is None
