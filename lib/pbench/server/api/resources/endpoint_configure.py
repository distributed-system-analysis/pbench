import re

from flask_restful import Resource, abort
from flask import request, jsonify
from urllib.parse import urljoin

from pbench.server.api.resources.query_apis import get_index_prefix


class EndpointConfig(Resource):
    """
    EndpointConfig API resource: this supports dynamic dashboard configuration
    from the Pbench server rather than constructing a disconnected dashboard
    config file.
    """

    def __init__(self, config, logger):
        """
        __init__ Construct the API resource

        Args:
            config (PbenchServerConfig): server config values
            logger (Logger): message logging

        Report the server configuration to a web client; web access can be
        redirected through an external reverse proxy like NGINX by setting
        the "proxy_host" configuration setting in the "pbench-server"
        section of the pbench-server.cfg file. By default, the Pbench
        server uses a local Apache reverse proxy routing through the HTTP
        port (80), but this can be changed to any host name and port. All
        server endpoints will be reported with respect to that address.
        """
        self.logger = logger
        self.host = config.get("pbench-server", "host")
        self.uri_prefix = config.rest_uri
        self.prefix = get_index_prefix(config)
        self.commit_id = config.COMMIT_ID
        self.forward_pattern = re.compile(r";\s*host\s*=\s*(?P<host>[^;\s]*)")
        self.x_forward_pattern = re.compile(r"^\s*(?P<host>[^;\s,]*)")

    def get(self):
        """
        Return server configuration information required by web clients
        including the Pbench dashboard UI. This includes:

        metadata: Information about the server configuration
            identification: The Pbench server name and version
            result_index: The "root" index name for Pbench result data,
                qualified by the current index version and prefix. In the
                current ES schema, this is "v5.result-data-sample."
            result_data_index: The "result-data" index has been broken into
                "result-data-sample" and "result-data" indices for the
                Elasticsearch V7 transition. In the current ES schema, this
                is "v5.result-data."
            run_index: The "master" run-data index root. In the current ES
                schema, this is "v6.run-data."
            run_toc_index: The Elasticsearch V7 index for run TOC data. In
                the current ES schema, this is "v6.run-toc."
        api:    A list of the server APIs supported; we give a name, which
                identifies the service, and the full URI relative to the
                configured host name and port (local or remote reverse proxy)
            results: Direct access to Pbench data sets for the dashboard; this
                is currently direct HTTP access through Apache public_html, and
                not an "API" as such; we will need to adopt this as a real
                server API when Pbench moves from local filesystem to S3 storage
                schemas
            elasticsearch: The Pbench pass-through URI for the Elasticsearch
                cluster. This will eventually be superceded by the native
                Pbench APIs, though it might remain accessible with special
                user/group privileges to support special cases
            graphql: The GraphQL frontend on postgreSQL currently used by the
                dashboard user mocks. This will be superceded and deprecated
                by native Pbench user management APIs
            queryControllers: Return information about the run documents that
                were created within a specified range of months.
            queryMonthIndices: Return the YYYY-mm date strings for all ES
                vx.run-data.* indices, in descending order

        TODO: We need an internal mechanism to track the active versions of the
        various Elasticsearch template documents. We're hardcoding them here and
        in other APIs. We should consider persisting an equivalent of the
        mapping table built in "indexer.py" for use across the server APIs.

        TODO: We provide Elasticsearch index root names here, which the dashboard
        code needs to perform the queries we've not yet replaced with server-side
        implementations. The entire "indices" section can be removed once that is
        resolved.
        """
        self.logger.info("Received these headers: {!r}", request.headers)
        header = request.headers.get("Forwarded")
        origin = None
        if header:
            m = self.forward_pattern.search(header)
            if m:
                origin = m.group("host")
                self.logger.info("Forwarded: {}, ({})", header, origin)
        if not origin:
            header = request.headers.get("X-Forwarded-Host")
            if header:
                m = self.x_forward_pattern.search(header)
                if m:
                    origin = m.group("host")
                    self.logger.info("X-Forwarded-Host: {}, ({})", header, origin)
        if not origin:
            origin = self.host
        host = f"http://{origin}"
        uri = urljoin(host, self.uri_prefix)
        self.logger.info("'{}' : '{}' : '{}' : '{}'", self.host, origin, host, uri)

        # Strip a trailing slash because the paths we'll add have an
        # initial slash and we don't want two.
        if uri.endswith("/"):
            uri = uri.split(0, -1)

        try:
            endpoints = {
                "identification": f"Pbench server {self.commit_id}",
                "indices": {
                    "run_index": f"{self.prefix}.v6.run-data.",
                    "run_toc_index": f"{self.prefix}.v6.run-toc.",
                    "result_index": f"{self.prefix}.v5.result-data-sample.",
                    "result_data_index": f"{self.prefix}.v5.result-data.",
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
            response = jsonify(endpoints)
        except Exception:
            self.logger.exception("Something went wrong constructing the endpoint info")
            abort(500, message="INTERNAL ERROR")
        else:
            response.status_code = 200
            return response
