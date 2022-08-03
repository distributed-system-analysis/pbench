import pytest
import logging
import jwt
from pbench.server.auth import KeycloakOpenID
from pbench.server.auth.keycloak_admin import Admin


@pytest.fixture
def keycloak_oidc(server_config):
    logger = logging.getLogger(__name__)
    oidc = KeycloakOpenID(
        server_url=server_config.get("keycloak", "server_url"),
        realm_name="public_test_realm",
        client_id="test_client",
        logger=logger,
    )
    return oidc


@pytest.fixture
def keycloak_admin(server_config):
    logger = logging.getLogger(__name__)
    return Admin(
        server_url=server_config.get("keycloak", "server_url"),
        realm_name="master",
        client_id="admin-cli",
        logger=logger,
        user_realm="public_test_realm",
    )


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
