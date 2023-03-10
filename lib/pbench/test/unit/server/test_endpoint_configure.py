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
                "datasets": f"{uri}/datasets",
                "datasets_contents": f"{uri}/datasets/contents",
                "datasets_daterange": f"{uri}/datasets/daterange",
                "datasets_detail": f"{uri}/datasets/detail",
                "datasets_inventory": f"{uri}/datasets/inventory",
                "datasets_list": f"{uri}/datasets",
                "datasets_mappings": f"{uri}/datasets/mappings",
                "datasets_metadata": f"{uri}/datasets/metadata",
                "datasets_namespace": f"{uri}/datasets/namespace",
                "datasets_search": f"{uri}/datasets/search",
                "datasets_values": f"{uri}/datasets/values",
                "endpoints": f"{uri}/endpoints",
                "login": f"{uri}/login",
                "logout": f"{uri}/logout",
                "register": f"{uri}/register",
                "server_audit": f"{uri}/server/audit",
                "server_settings": f"{uri}/server/settings",
                "upload": f"{uri}/upload",
                "user": f"{uri}/user",
            },
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
                "datasets_daterange": {
                    "template": f"{uri}/datasets/daterange",
                    "params": {},
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
                "login": {"template": f"{uri}/login", "params": {}},
                "logout": {"template": f"{uri}/logout", "params": {}},
                "register": {"template": f"{uri}/register", "params": {}},
                "server_audit": {"template": f"{uri}/server/audit", "params": {}},
                "server_settings": {
                    "template": f"{uri}/server/settings/{{key}}",
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

        try:
            oidc_client = server_config.get("openid-connect", "client")
            oidc_issuer = server_config.get("openid-connect", "server_url")
            oidc_realm = server_config.get("openid-connect", "realm")
            oidc_secret = server_config.get("openid-connect", "secret")
        except (NoOptionError, NoSectionError):
            pass
        else:
            expected_results["openid-connect"] = {
                "client": oidc_client,
                "issuer": oidc_issuer,
                "realm": oidc_realm,
                "secret": oidc_secret,
            }

        response = client.get(f"{server_config.rest_uri}/endpoints", headers=my_headers)
        res_json = response.json
        assert res_json == expected_results
