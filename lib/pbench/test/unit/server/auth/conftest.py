import jwt
import pytest

from pbench.server.auth import OpenIDClient
from pbench.server.globals import server


def mock_set_oidc_auth_endpoints(oidc_client):
    oidc_client.USERINFO_ENDPOINT = "https://oidc_userinfo_endpoint.example.com"
    oidc_client.TOKENINFO_ENDPOINT = "https://oidc_token_introspection.example.com"


def mock_get_oidc_public_key(oidc_client):
    return "-----BEGIN PUBLIC KEY-----\n" + "public_key" + "\n-----END PUBLIC KEY-----"


@pytest.fixture
def keycloak_oidc(server_config, server_logger, monkeypatch):
    monkeypatch.setattr(
        OpenIDClient, "set_well_known_endpoints", mock_set_oidc_auth_endpoints
    )
    monkeypatch.setattr(OpenIDClient, "_get_oidc_public_key", mock_get_oidc_public_key)
    oidc = OpenIDClient(
        server_url=server.config.get("authentication", "server_url"),
        realm_name="public_test_realm",
        client_id="test_client",
    )
    return oidc


@pytest.fixture
def keycloak_mock_token(server_config):
    payload = {
        "iat": 1659476706,
        "exp": 1685396687,
        "sub": "12345",
        "aud": "test_client",
    }

    # Get jwt key
    return jwt.encode(payload, key="some_secret", algorithm="HS256")
