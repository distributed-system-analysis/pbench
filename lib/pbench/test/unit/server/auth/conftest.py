import logging

import jwt
import pytest

from pbench.server.auth import OpenIDClient


def mock_set_oidc_auth_endpoints(oidc_client):
    oidc_client.USERINFO_ENDPOINT = "https://oidc_userinfo_endpoint.example.com"
    oidc_client.JWKS_ENDPOINT = "https://oidc_jwks_endpoint.example.com"


@pytest.fixture
def keycloak_oidc(server_config, monkeypatch):
    logger = logging.getLogger(__name__)
    monkeypatch.setattr(
        OpenIDClient, "set_well_known_endpoints", mock_set_oidc_auth_endpoints
    )
    oidc = OpenIDClient(
        server_url=server_config.get("keycloak", "server_url"),
        realm_name="public_test_realm",
        client_id="test_client",
        logger=logger,
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
