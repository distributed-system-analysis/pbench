import logging

from pbench.client import API, PbenchServerClient
from pbench.server.auth import OpenIDClient


class TestConnect:
    def test_connect(self, server_client: PbenchServerClient):
        """
        Verify that we can retrieve the Pbench Server endpoints through the
        client "connect" API, and that the expected APIs are described.
        """
        expected = [a.value for a in API]
        assert server_client.session
        assert server_client.session.headers["Accept"] == "application/json"
        endpoints = server_client.endpoints
        assert endpoints
        assert "api" in endpoints
        assert "authentication" in endpoints
        assert "identification" in endpoints
        assert "uri" in endpoints

        # Verify that all expected endpoints are reported
        for a in endpoints["api"].keys():
            assert a in expected
        for a in endpoints["uri"].keys():
            assert a in expected

        # Verify that no unexpected endpoints are reported
        for e in expected:
            assert e in endpoints["api"].keys()
            assert e in endpoints["uri"].keys()

    def test_keycloak(self, server_client: PbenchServerClient):
        endpoints = server_client.endpoints
        logger = logging.getLogger("FUNCTIONAL_TEST")
        oidc_client = OpenIDClient(
            server_url=endpoints["authentication"]["issuer"],
            client_id=endpoints["authentication"]["client"],
            realm_name=endpoints["authentication"]["realm"],
            client_secret_key=endpoints["authentication"]["secret"],
            logger=logger,
        )
        assert (
            oidc_client.TOKENINFO_ENDPOINT
            == "http://localhost:8090/realms/pbench/protocol/openid-connect/token/introspect"
        )
        assert (
            oidc_client.USERINFO_ENDPOINT
            == "http://localhost:8090/realms/pbench/protocol/openid-connect/userinfo"
        )
        assert (
            oidc_client.JWKS_URI
            == "http://localhost:8090/realms/pbench/protocol/openid-connect/certs"
        )
