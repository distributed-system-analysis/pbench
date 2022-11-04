from pbench.client import PbenchServerClient


class TestConnect:

    EXPECTED = (
        "datasets_contents",
        "datasets_daterange",
        "datasets_delete",
        "datasets_detail",
        "datasets_inventory",
        "datasets_list",
        "datasets_mappings",
        "datasets_metadata",
        "datasets_namespace",
        "datasets_publish",
        "datasets_search",
        "datasets_values",
        "elasticsearch",
        "endpoints",
        "login",
        "logout",
        "register",
        "server_configuration",
        "upload",
        "user",
    )

    def test_connect(self, pbench_server_client: PbenchServerClient):
        """
        Verify that we can retrieve the Pbench Server endpoints through the
        client "connect" API, and that the expected APIs are described.
        """
        assert pbench_server_client.session
        assert pbench_server_client.session.headers["Accept"] == "application/json"
        endpoints = pbench_server_client.endpoints
        assert endpoints
        assert "api" in endpoints
        assert "identification" in endpoints
        assert "uri" in endpoints
        for a in endpoints["api"].keys():
            assert a in self.EXPECTED
        for a in endpoints["uri"].keys():
            assert a in self.EXPECTED
