from urllib.parse import urljoin

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
        host = server_config.get("pbench-server", "host")
        self.check_config(client, server_config, host)

    def test_proxy_query(self, client, server_config):
        host = "proxy.example.com:8901"
        forward = f"by=server.example.com;for=client.example.com;host={host};proto=http"
        self.check_config(client, server_config, host, {"Forwarded": forward})

    def test_x_forward_proxy_query(self, client, server_config):
        host = "proxy.example.com:8902"
        self.check_config(client, server_config, host, {"X-Forwarded-Host": host})

    def test_x_forward_list_proxy_query(self, client, server_config):
        host1 = "proxy.example.com:8902"
        host2 = "proxy2.example.com"
        self.check_config(
            client, server_config, host1, {"X-Forwarded-Host": f"{host1}, {host2}"}
        )

    def check_config(self, client, server_config, host, my_headers={}):
        uri_prefix = server_config.rest_uri
        host = "http://" + host
        uri = urljoin(host, uri_prefix)
        prefix = get_index_prefix(server_config)
        expected_results = {
            "identification": f"Pbench server {server_config.COMMIT_ID}",
            "indices": {
                "run_index": f"{prefix}.v6.run-data.",
                "run_toc_index": f"{prefix}.v6.run-toc.",
                "result_index": f"{prefix}.v5.result-data-sample.",
                "result_data_index": f"{prefix}.v5.result-data.",
            },
            "api": {
                "results": f"{host}/results",
                "elasticsearch": f"{uri}/elasticsearch",
                "endpoints": f"{uri}/endpoints",
                "graphql": f"{uri}/graphql",
                "controller_list": f"{uri}/controllers/list",
                "controller_months": f"{uri}/controllers/months",
                "dataset_list": f"{uri}/datasets/list",
                "dataset": f"{uri}/datasets",
                "register": f"{uri}/register",
                "login": f"{uri}/login",
                "logout": f"{uri}/logout",
                "user": f"{uri}/user/<string:username>",
            },
        }

        response = client.get(f"{server_config.rest_uri}/endpoints", headers=my_headers)
        res_json = response.json
        assert res_json == expected_results
