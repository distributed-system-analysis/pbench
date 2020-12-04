from flask_restful import Resource, abort
from flask import jsonify

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
        """
        self.logger = logger
        port = config.get("pbench-server", "rest_port")
        host = config.get("pbench-server", "host")
        self.host = str(host)
        self.port = port
        uri_prefix = config.rest_uri
        self.uri = f"{host}:{port}{uri_prefix}"
        self.prefix = get_index_prefix(config)
        self.commit_id = config.COMMIT_ID

    def get(self):
        """
        Return server configuration information required by the UI
        dashboard. This includes

        metadata: Information about the server configuration
            prefix: The indexing prefix applied by the server to partition a
                shared Elasticsearch cluster index namespace.
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
                corresponds to either the current config.json property name
                (e.g., "elasticsearch") or the current src/service method name
                being replaced (e.g., "queryControllers").
            results: Direct access to Pbench data sets for the dashboard; this
                is likely also something that should be superceded, as Pbench
                will need to be a front-end for future S3 storage schemas.
            elasticsearch: The Pbench pass-through URI for the Elasticsearch
                cluster. This will eventually be superceded by the native
                Pbench APIs, though might remain accessible with special
                user/group privileges to support special cases?
            graphql: The GraphQL frontend on postgreSQL currently used by the
                dashboard user mocks. This will be superceded and decprecated
                by native Pbench user management APIs.
            queryControllers: Return information about the run documents that
                were created within a specified range of months.
            queryMonthIndices: Return the YYYY-mm date strings for all ES
                vx.run-data.* indices, in descending order.


        Meta TODO: We're giving the pass-through APIs for Elasticsearch and
        GraphQL here, which implies adoption of Nikhil's and Fuqing's work to
        move the dashboard away from direct access to the backend DB servers.
        The alternative would be to expose the direct Elasticsearch and GraphQL
        URIs here.
        """
        try:
            endpoints = {
                "metadata": {
                    "identification": f"Pbench server {self.commit_id}",
                    "prefix": self.prefix,
                    "run_index": f"{self.prefix}.v6.run-data.",
                    "run_toc_index": f"{self.prefix}.v6.run-toc.",
                    "result_index": f"{self.prefix}.v5.result-data-sample.",
                    "result_data_index": f"{self.prefix}.v5.result-data.",
                },
                "api": {
                    "results": f"{self.host}:8901",
                    "elasticsearch": f"{self.uri}/elasticsearch",
                    "endpoints": f"{self.uri}/endpoints",
                    "graphql": f"{self.uri}/graphql",
                    "queryControllers": f"{self.uri}/controllers/list",
                    "queryMonthIndices": f"{self.uri}/controllers/months",
                },
            }
            response = jsonify(endpoints)
        except Exception:
            self.logger.exception("Something went wrong constructing the endpoint info")
            abort(500, message="INTERNAL ERROR")
        else:
            response.status_code = 200
            return response
