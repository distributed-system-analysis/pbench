from pbench.client import API, PbenchServerClient


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
        assert "identification" in endpoints
        assert "uri" in endpoints

        # Verify that all expected endpoints are reported
        for a in endpoints["uri"].keys():
            assert a in expected

        # Verify that no unexpected endpoints are reported
        for e in expected:
            assert e in endpoints["uri"].keys()

        # verify all the required openid-connect fields are present
        oid_ep = set(endpoints.get("openid", {}))
        assert oid_ep >= {"client", "realm", "server"} or not oid_ep
