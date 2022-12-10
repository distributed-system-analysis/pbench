import datetime

from flask import Flask
import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAlgorithmError,
    InvalidAudienceError,
    InvalidTokenError,
)
import pytest

from pbench.server.auth import OpenIDClient
from pbench.server.auth.auth import Auth, InternalUser


class TestUserTokenManagement:
    USERNAME = "test"
    PASSWORD = "test123"
    REALM_NAME = "public_test_realm"

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
        with pytest.raises(InvalidAudienceError) as e:
            keycloak_oidc.token_introspect_offline(
                token=keycloak_mock_token,
                key="some_secret",
                algorithms=["HS256"],
                audience="wrong_client",
                options=options,
            )
        assert str(e.value) == "Invalid audience"

    def test_token_introspect_invalid_algorithm(
        self, keycloak_oidc, keycloak_mock_token
    ):
        options = {"verify_signature": True, "verify_aud": True, "verify_exp": True}
        with pytest.raises(InvalidAlgorithmError) as e:
            keycloak_oidc.token_introspect_offline(
                token=keycloak_mock_token,
                key="some_secret",
                algorithms=["INVALID_ALGORITHM"],
                audience="wrong_client",
                options=options,
            )
        assert str(e.value) == "The specified alg value is not allowed"

    def test_token_introspect_expired_signature(self, keycloak_oidc):
        current_utc = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "iat": current_utc,
            "exp": current_utc - datetime.timedelta(minutes=1),  # expired token
            "sub": "12345",
            "aud": "test_client",
        }

        # Get jwt key
        token = jwt.encode(payload, key="some_secret", algorithm="HS256")
        options = {"verify_signature": True, "verify_aud": True, "verify_exp": True}
        with pytest.raises(ExpiredSignatureError) as e:
            keycloak_oidc.token_introspect_offline(
                token=token,
                key="some_secret",
                algorithms=["HS256"],
                audience="wrong_client",
                options=options,
            )
        assert str(e.value) == "Signature has expired"

    def test_token_introspect_invalid_token(self, monkeypatch, keycloak_oidc):
        def offline_token_introspection_exception(
            self, token: str, key: str, audience: str
        ):
            raise InvalidTokenError("Invalid token")

        monkeypatch.setattr(
            OpenIDClient,
            "token_introspect_offline",
            offline_token_introspection_exception,
        )
        with pytest.raises(InvalidTokenError) as e:
            keycloak_oidc.token_introspect_offline(
                token="token",
                key="some_secret",
                audience="wrong_client",
            )
        assert str(e.value) == "Invalid token"

    def test_online_third_party_verification(
        self,
        server_config,
        make_logger,
        monkeypatch,
        keycloak_oidc,
        keycloak_mock_token,
    ):
        def offline_token_introspection_exception(token: str, key: str, audience: str):
            raise Exception("some exception")

        monkeypatch.setattr(
            OpenIDClient,
            "token_introspect_offline",
            offline_token_introspection_exception,
        )

        def fake_online_token_introspection(self, token: str, token_info_uri: str):
            return {
                "iat": 1659476706,
                "exp": 1685396687,
                "sub": "12345",
                "aud": "test_client",
                "name": "first_name last_name",
                "preferred_username": "username",
                "given_name": "first_name",
                "family_name": "last_name",
                "email": "email",
            }

        monkeypatch.setattr(
            OpenIDClient, "token_introspect_online", fake_online_token_introspection
        )
        app = Flask("test-verify-third-party-token")
        app.logger = make_logger
        with app.app_context():
            token_payload = Auth.verify_third_party_token(
                auth_token="",
                algorithms=["HS256"],
                oidc_client=keycloak_oidc,
            )
        assert token_payload == InternalUser(
            id="12345",
            username="username",
            email="email",
            first_name="first_name",
            last_name="last_name",
            roles=[],
        )
