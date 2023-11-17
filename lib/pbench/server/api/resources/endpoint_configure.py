from typing import Any
from urllib.parse import urljoin

from flask import current_app, jsonify, Request, Response
from pquisby.lib.post_processing import BenchmarkName

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    ApiBase,
    ApiContext,
    APIInternalError,
    ApiMethod,
    ApiParams,
    ApiSchema,
)


class EndpointConfig(ApiBase):
    """
    This supports dynamic dashboard configuration from the Pbench server rather
    than constructing a static dashboard config file.
    """

    def __init__(self, config: PbenchServerConfig):
        """
        __init__ Construct the API resource

        Args:
            config: server config values

        Report the server configuration to a web client. By default, the Pbench
        server ansible script sets up a local Apache reverse proxy routing
        through the HTTP port (80); an external reverse-proxy can be configured
        without the knowledge of the server, and this API will try to use the
        reverse-proxy Forwarded or X-Forwarded-Host HTTP headers to discover
        preferred HTTP address of the server.

        If neither forwarding header is present, this API will use the `host`
        attribute from the Flask `Requests` object, which records how the
        client directed the request.

        All server endpoints will be reported with respect to the identified
        address. This means subsequent client API calls will preserve whatever
        proxying was set up for the original endpoints query: e.g., the
        Javascript `window.origin` from which the Pbench dashboard was loaded.
        """
        super().__init__(config, ApiSchema(ApiMethod.GET, OperationCode.READ))
        self.server_config = config

    def _get(self, args: ApiParams, req: Request, context: ApiContext) -> Response:
        """
        Return server configuration information required by web clients
        including the Pbench dashboard UI. This includes:

        openid: A JSON object containing the OpenID Connect parameters
                required for the web client to use OIDC authentication.
        identification: The Pbench server name and version
        uri:    A dict of server API templates, where each template defines a
                template URI and a list of typed parameters.

        We derive a "name" for each API by removing URI parameters and the API
        prefix (/api/v1/), then replacing the path "/" characters with
        underscores.

        The "uri" object defines a template for each API name, defining a set of
        URI parameters that must be expanded in the template. For example, the
        API to get or modify metadata is:

            {
                "template": "https://host/api/v1/datasets/{dataset}/metadata",
                "params": {"dataset": {"type": "string"}}
            }

        The template can be resolved in Python with:

            template.format(target_username="value")

        Or in Javascript with:

            template.replace('{target_username}', 'value')
        """
        origin = self._get_uri_base(req)
        current_app.logger.info(
            "Advertising endpoints at {} relative to {} ({})",
            origin.host,
            origin.host_source,
            origin.host_value,
        )

        host = origin.host

        templates = {}

        # Iterate through the Flask endpoints to add a description for each.
        for rule in current_app.url_map.iter_rules():
            url = str(rule.rule)

            # Ignore anything that doesn't use our API prefix, because it's
            # not in our API.
            if url.startswith(self.server_config.rest_uri):
                simplified = self.PARAM_TEMPLATE.sub(r"/{\g<name>}", url)
                matches = self.PARAM_TEMPLATE.finditer(url)
                template: dict[str, Any] = {
                    "template": urljoin(host, simplified),
                    "params": {
                        match.group("name"): {"type": match.group("type")}
                        for match in matches
                    },
                }
                path = rule.endpoint

                # We have some URI endpoints that repeat a basic URI pattern.
                # The "primary" may have several URI parameters; the others
                # have fewer parameters (e.g., "/x/{p}" and "/x" or
                # "/x/{p}/{n}" and "/x/{p}" and "/x") and won't capture all
                # the information we want. So we only keep the variant with the
                # highest parameter count.
                if path not in templates or (
                    len(template["params"]) > len(templates[path]["params"])
                ):
                    templates[path] = template

        endpoints = {
            "identification": f"Pbench server {self.server_config.COMMIT_ID}",
            "uri": templates,
            "visualization": {
                "benchmarks": sorted(
                    m.lower() for m in BenchmarkName.__members__.keys()
                )
            },
        }

        client = self.server_config.get("openid", "client")
        realm = self.server_config.get("openid", "realm")
        server = self.server_config.get("openid", "server_url")

        endpoints["openid"] = {
            "client": client,
            "realm": realm,
            "server": server,
        }

        try:
            return jsonify(endpoints)
        except Exception:
            APIInternalError("Something went wrong constructing the endpoint info")
