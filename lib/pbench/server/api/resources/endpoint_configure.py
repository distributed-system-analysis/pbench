from configparser import NoOptionError, NoSectionError
from http import HTTPStatus
import re
from typing import Any, Dict
from urllib.parse import urljoin

from flask import current_app, jsonify, request
from flask_restful import abort, Resource

from pbench.server import PbenchServerConfig


class EndpointConfig(Resource):
    """
    This supports dynamic dashboard configuration from the Pbench server rather
    than constructing a static dashboard config file.
    """

    forward_pattern = re.compile(r";\s*host\s*=\s*(?P<host>[^;\s]+)")
    x_forward_pattern = re.compile(r"\s*(?P<host>[^;\s,]+)")
    param_template = re.compile(r"/<(?P<type>[^:]+):(?P<name>\w+)>")

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
        self.server_config = config

    def get(self):
        """
        Return server configuration information required by web clients
        including the Pbench dashboard UI. This includes:

        openid-connect: A JSON object containing the OpenID Connect parameters
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
                "template": "http://host/api/v1/datasets/{dataset}/metadata",
                "params": {"dataset": {"type": "string"}}
            }

        The template can be resolved in Python with:

            template.format(target_username="value")

        Or in Javascript with:

            template.replace('{target_username}', 'value')
        """
        current_app.logger.debug(
            "Received headers: {!r}, access_route {!r}, base_url {!r}, host {!r}, host_url {!r}",
            request.headers,
            request.access_route,
            request.base_url,
            request.host,
            request.host_url,
        )
        origin = None
        host_source = "request"
        host_value = request.host
        header = request.headers.get("Forwarded")
        if header:
            m = self.forward_pattern.search(header)
            if m:
                origin = m.group("host")
                host_source = "Forwarded"
                host_value = header
        if not origin:
            header = request.headers.get("X-Forwarded-Host")
            if header:
                m = self.x_forward_pattern.match(header)
                if m:
                    origin = m.group("host")
                    host_source = "X-Forwarded-Host"
                    host_value = header
        if not origin:
            origin = host_value
        host = f"{request.headers.get('X-Forwarded-Proto')}://{origin}"
        current_app.logger.info(
            "Advertising endpoints at {} relative to {} ({})",
            host,
            host_source,
            host_value,
        )

        templates = {}

        # Iterate through the Flask endpoints to add a description for each.
        for rule in current_app.url_map.iter_rules():
            url = str(rule.rule)

            # Ignore anything that doesn't use our API prefix, because it's
            # not in our API.
            if url.startswith(self.server_config.rest_uri):
                simplified = self.param_template.sub(r"/{\g<name>}", url)
                matches = self.param_template.finditer(url)
                template: Dict[str, Any] = {
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
        }

        try:
            client = self.server_config.get("openid", "client")
            realm = self.server_config.get("openid", "realm")
            server = self.server_config.get("openid", "server_url")
        except (NoOptionError, NoSectionError):
            pass
        else:
            endpoints["openid"] = {
                "client": client,
                "realm": realm,
                "server": server,
            }

        try:
            response = jsonify(endpoints)
        except Exception:
            current_app.logger.exception(
                "Something went wrong constructing the endpoint info"
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        else:
            response.status_code = HTTPStatus.OK
            return response
