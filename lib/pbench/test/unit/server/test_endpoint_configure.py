from configparser import NoOptionError, NoSectionError
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
        self.check_config(
            client,
            server_config,
            host,
            {"Forwarded": forward, "X-Forwarded-Proto": "https"},
        )

    def test_x_forward_proxy_query(self, client, server_config):
        host = "proxy.example.com:8902"
        self.check_config(
            client,
            server_config,
            host,
            {"X-Forwarded-Host": host, "X-Forwarded-Proto": "https"},
        )

    def test_x_forward_list_proxy_query(self, client, server_config):
        host1 = "proxy.example.com:8902"
        host2 = "proxy2.example.com"
        self.check_config(
            client,
            server_config,
            host1,
            {"X-Forwarded-Host": f"{host1}, {host2}", "X-Forwarded-Proto": "https"},
        )

    def check_config(self, client, server_config, host, my_headers={}):
        uri_prefix = server_config.rest_uri
        host = "https://" + host
        uri = urljoin(host, uri_prefix)
        expected_results = {
            "identification": f"Pbench server {server_config.COMMIT_ID}",
            "uri": {
                "datasets": {
                    "template": f"{uri}/datasets/{{dataset}}",
                    "params": {"dataset": {"type": "string"}},
                },
                "datasets_contents": {
                    "template": f"{uri}/datasets/{{dataset}}/contents/{{target}}",
                    "params": {
                        "dataset": {"type": "string"},
                        "target": {"type": "path"},
                    },
                },
                "datasets_detail": {
                    "template": f"{uri}/datasets/{{dataset}}/detail",
                    "params": {"dataset": {"type": "string"}},
                },
                "datasets_inventory": {
                    "template": f"{uri}/datasets/{{dataset}}/inventory/{{target}}",
                    "params": {
                        "dataset": {"type": "string"},
                        "target": {"type": "path"},
                    },
                },
                "datasets_list": {"template": f"{uri}/datasets", "params": {}},
                "datasets_mappings": {
                    "template": f"{uri}/datasets/mappings/{{dataset_view}}",
                    "params": {"dataset_view": {"type": "string"}},
                },
                "datasets_metadata": {
                    "template": f"{uri}/datasets/{{dataset}}/metadata",
                    "params": {"dataset": {"type": "string"}},
                },
                "datasets_namespace": {
                    "template": f"{uri}/datasets/{{dataset}}/namespace/{{dataset_view}}",
                    "params": {
                        "dataset": {"type": "string"},
                        "dataset_view": {"type": "string"},
                    },
                },
                "datasets_search": {"template": f"{uri}/datasets/search", "params": {}},
                "datasets_values": {
                    "template": f"{uri}/datasets/{{dataset}}/values/{{dataset_view}}",
                    "params": {
                        "dataset": {"type": "string"},
                        "dataset_view": {"type": "string"},
                    },
                },
                "endpoints": {"template": f"{uri}/endpoints", "params": {}},
                "key": {
                    "template": f"{uri}/key/{{key}}",
                    "params": {"key": {"type": "string"}},
                },
                "quisby": {
                    "template": f"{uri}/quisby/{{dataset}}",
                    "params": {"dataset": {"type": "string"}},
                },
                "relay": {
                    "template": f"{uri}/relay/{{uri}}",
                    "params": {"uri": {"type": "path"}},
                },
                "server_audit": {"template": f"{uri}/server/audit", "params": {}},
                "server_settings": {
                    "template": f"{uri}/server/settings/{{key}}",
                    "params": {"key": {"type": "string"}},
                },
                "upload": {
                    "template": f"{uri}/upload/{{filename}}",
                    "params": {"filename": {"type": "string"}},
                },
            },
        }

        try:
            oidc_client = server_config.get("openid", "client")
            oidc_realm = server_config.get("openid", "realm")
            oidc_server = server_config.get("openid", "server_url")
        except (NoOptionError, NoSectionError):
            pass
        else:
            expected_results["openid"] = {
                "client": oidc_client,
                "realm": oidc_realm,
                "server": oidc_server,
            }

        response = client.get(f"{server_config.rest_uri}/endpoints", headers=my_headers)
        res_json = response.json
        assert res_json == expected_results
