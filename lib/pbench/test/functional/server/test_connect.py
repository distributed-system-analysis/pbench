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
        "graphql",
        "login",
        "logout",
        "register",
        "upload",
        "user",
    )

    def test_endpoints(self, pbench):
        """
        Verify that we can retrieve the Pbench Server endpoints through the
        client "connect" API, and that the expected APIs are described.
        """
        endpoints = pbench.endpoints
        assert endpoints
        assert "api" in endpoints
        for a in endpoints["api"].keys():
            assert a in self.EXPECTED
        for a in endpoints["uri"].keys():
            assert a in self.EXPECTED
        assert "identification" in endpoints
        assert "uri" in endpoints
