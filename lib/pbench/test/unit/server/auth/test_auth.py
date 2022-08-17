from jwt.exceptions import InvalidAudienceError
import pytest
import responses
from pbench.server.auth.exceptions import OpenIDCAuthenticationError


class TestUserTokenManagement:
    USERNAME = "test"
    PASSWORD = "test123"
    REALM_NAME = "public_test_realm"

    @responses.activate
    def test_get_user_token(self, server_config, keycloak_oidc):
        token_endpoint = keycloak_oidc.TOKEN_ENDPOINT

        json_response = {
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIi",
            "expires_in": 300,
            "refresh_expires_in": 1800,
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA",
            "token_type": "Bearer",
            "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwiPt_h5LI707",
            "not-before-policy": 0,
            "session_state": "a46aca36-78e3-4b2a-90b3-7bd46d5ff70d",
            "scope": "openid profile email",
        }
        responses.add(
            responses.POST,
            token_endpoint,
            status=200,
            json=json_response,
        )
        token_response = keycloak_oidc.get_user_token(
            username=self.USERNAME, password=self.PASSWORD
        )
        assert token_response["access_token"] == json_response["access_token"]

    @responses.activate
    def test_invalid_user_credential(self, server_config, keycloak_oidc):
        token_endpoint = keycloak_oidc.TOKEN_ENDPOINT
        json_response = {
            "error": "invalid_grant",
            "error_description": "Invalid user credentials",
        }
        responses.add(
            responses.POST,
            token_endpoint,
            status=401,
            json=json_response,
        )
        with pytest.raises(OpenIDCAuthenticationError) as e:
            keycloak_oidc.get_user_token(username=self.USERNAME, password="wrong_pass")
        assert str(e.value) == "Unauthorized"

    def test_token_introspect_offline(self, keycloak_oidc, keycloak_mock_token):
        options = {"verify_signature": True, "verify_aud": True, "verify_exp": True}
        response = keycloak_oidc.token_introspect_offline(
            token=keycloak_mock_token,
            key="some_secret",
            algorithms=["HS256"],
            audience="test_client",
            options=options,
        )
        assert response == {
            "iat": 1659476706,
            "exp": 1685396687,
            "sub": "12345",
            "aud": "test_client",
        }

    def test_token_introspect_wrong_aud_claim(self, keycloak_oidc, keycloak_mock_token):
        options = {"verify_signature": True, "verify_aud": True, "verify_exp": True}
        with pytest.raises(InvalidAudienceError):
            keycloak_oidc.token_introspect_offline(
                token=keycloak_mock_token,
                key="some_secret",
                algorithms=["HS256"],
                audience="wrong_client",
                options=options,
            )

    @responses.activate
    def test_get_userinfo(self, server_config, keycloak_oidc, keycloak_mock_token):
        userinfo_endpoint = keycloak_oidc.USERINFO_ENDPOINT
        json_response = {
            "sub": "d0d1338c-f0df-4493-b9f2-078eedc1e02e",
            "email_verified": False,
            "name": "test pbench",
            "preferred_username": "test",
            "given_name": "test",
            "family_name": "pbench",
            "email": "test@example.com",
        }

        responses.add(
            responses.GET,
            userinfo_endpoint,
            status=200,
            json=json_response,
        )
        token_response = keycloak_oidc.get_userinfo(token=keycloak_mock_token)
        assert token_response["sub"] == json_response["sub"]
