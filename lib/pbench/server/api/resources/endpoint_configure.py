from configparser import NoOptionError, NoSectionError
from http import HTTPStatus
import re
from typing import Any, Dict
from urllib.parse import urljoin

from flask import current_app, jsonify, request
from flask_restful import abort, Resource

from pbench.server.globals import server


class EndpointConfig(Resource):
    """
    This supports dynamic dashboard configuration from the Pbench server rather
    than constructing a static dashboard config file.
    """

    endpoint = "endpoints"
    urls = ["endpoints"]

    forward_pattern = re.compile(r";\s*host\s*=\s*(?P<host>[^;\s]+)")
    x_forward_pattern = re.compile(r"\s*(?P<host>[^;\s,]+)")
    param_template = re.compile(r"/<(?P<type>[^:]+):(?P<name>\w+)>")

    def get(self):
        """Report the server configuration to a client, include the Pbench
        dashboard UI. By default, the Pbench server is deployed behind a
        reverse proxy routing through the port (8080); an external
        reverse-proxy can be configured without the knowledge of the server,
        and this API will try to use the reverse-proxy Forwarded or
        X-Forwarded-Host HTTP headers to discover preferred HTTP address of
        the server.

        If neither forwarding header is present, this API will use the `host`
        attribute from the Flask `Requests` object, which records how the
        client directed the request.

        All server endpoints will be reported with respect to the identified
        address. This means subsequent client API calls will preserve whatever
        proxying was set up for the original endpoints query: e.g., the
        Javascript `window.origin` from which the Pbench dashboard was loaded.

        The server configuration information returned includes:

        openid-connect: A JSON object containing the OpenID Connect parameters
                        required for the web client to use OIDC authentication.
        identification: The Pbench server name and version
        api:    A dict of the server APIs supported; we give a name, which
                identifies the service, and the full URI relative to the
                configured host name and port (local or remote reverse proxy).

                This is dynamically generated by processing the Flask URI
                rules; refer to api/__init__.py for the code which creates
                those mappings, or test_endpoint_configure.py for code that
                validates the current set (and must be updated when the API
                set changes).
        uri:    A dict of server API templates, where each template defines a
                template URI and a list of typed parameters.

        We derive a "name" for each API by removing URI parameters and the API
        prefix (/api/v1/), then replacing the path "/" characters with
        underscores.

        The "api" object contains a key for each API name, where the value is a
        simplified URI omitting URI parameters. The client must either know the
        required parameters and order, and connect them to the "api" value
        separated by slash characters, or refer to the "uri" templates.

        E.g, "/api/v1/controllers/list" yields:

            "controllers_list": "http://host/api/v1/controllers/list"

        while "/api/v1/users/<string:username>" yields:

            "users": "http://host/api/v1/users"

        For URIs with multiple parameters, or embedded parameters, it may be
        easier to work with the template string in the "uri" object. The value
        of each API name key in the "uri" object is a minimal "schema" object
        defining the template string and parameters for the API. The "uri"
        value for the "users" API, for example, will be

            {
                "template": "http://host/api/v1/users/{target_username}",
                "params": {"target_username": {"type": "string"}}
            }

        The template can be resolved in Python with:

            template.format(target_username="value")

        Or in Javascript with:

            template.replace('{target_username}', 'value')

        """
        server.logger.debug(
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
        host = f"http://{origin}"
        server.logger.info(
            "Advertising endpoints at {} relative to {} ({})",
            host,
            host_source,
            host_value,
        )

        apis = {}
        templates = {}

        # Iterate through the Flask endpoints to add a description for each.
        for rule in current_app.url_map.iter_rules():
            url = str(rule.rule)

            # Ignore anything that doesn't use our API prefix, because it's
            # not in our API.
            if url.startswith(server.config.rest_uri):
                simplified = self.param_template.sub(r"/{\g<name>}", url)
                matches = self.param_template.finditer(url)
                template: Dict[str, Any] = {
                    "template": urljoin(host, simplified),
                    "params": {
                        match.group("name"): {"type": match.group("type")}
                        for match in matches
                    },
                }
                url = self.param_template.sub("", url)
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
                    apis[path] = urljoin(host, url)
                    templates[path] = template

        endpoints = {
            "identification": f"Pbench server {server.config.COMMIT_ID}",
            "api": apis,
            "uri": templates,
        }

        try:
            secret = server.config.get("openid-connect", "secret")
            client = server.config.get("openid-connect", "client")
            realm = server.config.get("openid-connect", "realm")
            issuer = server.config.get("openid-connect", "server_url")
        except (NoOptionError, NoSectionError):
            pass
        else:
            endpoints["openid-connect"] = {
                "client": client,
                "realm": realm,
                "issuer": issuer,
                "secret": secret,
            }

        try:
            response = jsonify(endpoints)
        except Exception:
            server.logger.exception(
                "Something went wrong constructing the endpoint info"
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        else:
            response.status_code = HTTPStatus.OK
            return response
