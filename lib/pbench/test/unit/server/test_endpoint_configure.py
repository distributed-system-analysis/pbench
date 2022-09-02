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
        auth_realm = server_config.get("authentication", "realm")
        auth_issuer = (
            server_config.get("authentication", "server_url") + f"/{auth_realm}"
        )
        auth_obj = {
            "realm": auth_realm,
            "client": server_config.get("authentication", "client"),
            "issuer": auth_issuer,
            "secret": "",
        }
        expected_results = {
            "authentication": auth_obj,
            "identification": f"Pbench server {server_config.COMMIT_ID}",
            "api": {
                "datasets_contents": f"{uri}/datasets/contents",
                "datasets_daterange": f"{uri}/datasets/daterange",
                "datasets_delete": f"{uri}/datasets/delete",
                "datasets_detail": f"{uri}/datasets/detail",
                "datasets_inventory": f"{uri}/datasets/inventory",
                "datasets_list": f"{uri}/datasets/list",
                "datasets_mappings": f"{uri}/datasets/mappings",
                "datasets_metadata": f"{uri}/datasets/metadata",
                "datasets_namespace": f"{uri}/datasets/namespace",
                "datasets_publish": f"{uri}/datasets/publish",
                "datasets_search": f"{uri}/datasets/search",
                "datasets_values": f"{uri}/datasets/values",
                "endpoints": f"{uri}/endpoints",
                "graphql": f"{uri}/graphql",
                "login": f"{uri}/login",
                "logout": f"{uri}/logout",
                "register": f"{uri}/register",
                "server_configuration": f"{uri}/server/configuration",
                "upload": f"{uri}/upload",
                "user": f"{uri}/user",
            },
            "uri": {
                "datasets_contents": {
                    "template": f"{uri}/datasets/contents/{{dataset}}/{{target}}",
                    "params": {
                        "dataset": {"type": "string"},
                        "target": {"type": "path"},
                    },
                },
                "datasets_daterange": {
                    "template": f"{uri}/datasets/daterange",
                    "params": {},
                },
                "datasets_delete": {
                    "template": f"{uri}/datasets/delete/{{dataset}}",
                    "params": {"dataset": {"type": "string"}},
                },
                "datasets_detail": {
                    "template": f"{uri}/datasets/detail/{{dataset}}",
                    "params": {"dataset": {"type": "string"}},
                },
                "datasets_inventory": {
                    "template": f"{uri}/datasets/inventory/{{dataset}}/{{target}}",
                    "params": {
                        "dataset": {"type": "string"},
                        "target": {"type": "path"},
                    },
                },
                "datasets_list": {"template": f"{uri}/datasets/list", "params": {}},
                "datasets_mappings": {
                    "template": f"{uri}/datasets/mappings/{{dataset_view}}",
                    "params": {"dataset_view": {"type": "string"}},
                },
                "datasets_metadata": {
                    "template": f"{uri}/datasets/metadata/{{dataset}}",
                    "params": {"dataset": {"type": "string"}},
                },
                "datasets_namespace": {
                    "template": f"{uri}/datasets/namespace/{{dataset}}/{{dataset_view}}",
                    "params": {
                        "dataset": {"type": "string"},
                        "dataset_view": {"type": "string"},
                    },
                },
                "datasets_publish": {
                    "template": f"{uri}/datasets/publish/{{dataset}}",
                    "params": {"dataset": {"type": "string"}},
                },
                "datasets_search": {"template": f"{uri}/datasets/search", "params": {}},
                "datasets_values": {
                    "template": f"{uri}/datasets/values/{{dataset}}/{{dataset_view}}",
                    "params": {
                        "dataset": {"type": "string"},
                        "dataset_view": {"type": "string"},
                    },
                },
                "endpoints": {"template": f"{uri}/endpoints", "params": {}},
                "graphql": {"template": f"{uri}/graphql", "params": {}},
                "login": {"template": f"{uri}/login", "params": {}},
                "logout": {"template": f"{uri}/logout", "params": {}},
                "register": {"template": f"{uri}/register", "params": {}},
                "server_configuration": {
                    "template": f"{uri}/server/configuration/{{key}}",
                    "params": {"key": {"type": "string"}},
                },
                "upload": {
                    "template": f"{uri}/upload/{{filename}}",
                    "params": {"filename": {"type": "string"}},
                },
                "user": {
                    "template": f"{uri}/user/{{target_username}}",
                    "params": {"target_username": {"type": "string"}},
                },
            },
        }

        response = client.get(f"{server_config.rest_uri}/endpoints", headers=my_headers)
        res_json = response.json
        assert res_json == expected_results
