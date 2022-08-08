import pytest
import responses
from jwt.exceptions import InvalidAudienceError


def mock_set_oidc_auth_endpoints(oidc_client):
    oidc_client.TOKEN_ENDPOINT = "https://oidc_token.endpoint.com"
    oidc_client.USERINFO_ENDPOINT = "https://oidc_userinfo_endpoint.com"
    oidc_client.REVOCATION_ENDPOINT = "https://oidc_revocation_endpoint.com"
    oidc_client.JWKS_ENDPOINT = "https://oidc_jwks_endpoint.com"


class TestUserTokenManagement:
    USERNAME = "test"
    PASSWORD = "test123"
    REALM_NAME = "public_test_realm"

    @responses.activate
    def test_get_token(self, server_config, keycloak_oidc):
        mock_set_oidc_auth_endpoints(keycloak_oidc)
        token_endpoint = keycloak_oidc.TOKEN_ENDPOINT

        json_response = {
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJDeXVpZDFYU2F3eEJSNlp2azdNOXZBUnI3R3pUWnE2QlpDQjNra2hGMHRVIn0",
            "expires_in": 300,
            "refresh_expires_in": 1800,
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJlNGVlMzc2Ni1mNTVkL",
            "token_type": "Bearer",
            "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwiPt_h5LI707x4JLFCBeUMaYSkPhQrmXz2QQZ5qpD60Yo7w",
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
        mock_set_oidc_auth_endpoints(keycloak_oidc)
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
        token_response = keycloak_oidc.get_user_token(
            username=self.USERNAME, password="wrong_pass"
        )
        assert token_response["error"] == json_response["error"]

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
    def test_userinfo(self, server_config, keycloak_oidc, keycloak_mock_token):
        mock_set_oidc_auth_endpoints(keycloak_oidc)
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
