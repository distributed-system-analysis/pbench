from urllib.parse import urljoin


class TestEndpointConfig:
    """
    Unit testing for EndpointConfig class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def test_query(self, client, server_config):
        """
        test_query Check that endpoint data matches the config file. In the
        local Flask mocked environment, `request.host` will always be
        "localhost".
        """
        self.check_config(client, server_config, "localhost")

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
        expected_results = {
            "identification": f"Pbench server {server_config.COMMIT_ID}",
            "api": {
                # API endpoints with trailing Flask parameters are marked with
                # a trailing "/" here; for example, /datasets/mappings/
                # corresponds to /datasets/mappings/<string:dataset_view>";
                # see endpoint_configure.py for more detail.
                "datasets_contents": f"{uri}/datasets/contents",
                "datasets_daterange": f"{uri}/datasets/daterange",
                "datasets_delete": f"{uri}/datasets/delete",
                "datasets_detail": f"{uri}/datasets/detail/",
                "datasets_list": f"{uri}/datasets/list",
                "datasets_mappings": f"{uri}/datasets/mappings/",
                "datasets_metadata": f"{uri}/datasets/metadata/",
                "datasets_namespace": f"{uri}/datasets/namespace/",
                "datasets_publish": f"{uri}/datasets/publish",
                "datasets_search": f"{uri}/datasets/search",
                "datasets_values": f"{uri}/datasets/values/",
                "elasticsearch": f"{uri}/elasticsearch",
                "endpoints": f"{uri}/endpoints",
                "graphql": f"{uri}/graphql",
                "login": f"{uri}/login",
                "logout": f"{uri}/logout",
                "register": f"{uri}/register",
                "results": f"{host}/results",
                "upload": f"{uri}/upload/",
                "user": f"{uri}/user/",
            },
        }

        response = client.get(f"{server_config.rest_uri}/endpoints", headers=my_headers)
        res_json = response.json
        assert res_json == expected_results
