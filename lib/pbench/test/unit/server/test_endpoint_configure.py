from pbench.server.api.resources.query_apis import get_index_prefix


class TestEnpointConfig:
    """
    Unit testing for EndpointConfig class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def test_query(self, client, server_config):
        """
        test_query Check that endpoint data matches the config file.
        """
        port = server_config.get("pbench-server", "rest_port")
        host = server_config.get("pbench-server", "host")
        uri_prefix = server_config.rest_uri
        uri = f"{host}:{port}{uri_prefix}"
        prefix = get_index_prefix(server_config)
        expected_results = {
            "metadata": {
                "identification": f"Pbench server {server_config.COMMIT_ID}",
                "prefix": prefix,
                "run_index": f"{prefix}.v6.run-data.",
                "run_toc_index": f"{prefix}.v6.run-toc.",
                "result_index": f"{prefix}.v5.result-data-sample.",
                "result_data_index": f"{prefix}.v5.result-data.",
            },
            "api": {
                "results": f"{host}:8901",
                "elasticsearch": f"{uri}/elasticsearch",
                "endpoints": f"{uri}/endpoints",
                "graphql": f"{uri}/graphql",
                "queryControllers": f"{uri}/controllers/list",
                "queryMonthIndices": f"{uri}/controllers/months",
            },
        }

        response = client.get(f"{server_config.rest_uri}/endpoints")
        res_json = response.json
        assert res_json == expected_results
