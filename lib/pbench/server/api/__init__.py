"""
Pbench Server API module -
Provides middleware for remote clients, either the associated Pbench
Dashboard or any number of pbench agent users.
"""

import os

from flask import Flask
from flask_restful import Api

from pbench.server import PbenchServerConfig
from pbench.common.exceptions import BadConfig, ConfigFileNotSpecified
from pbench.server.api.resources.upload_api import Upload, HostInfo
from pbench.server.api.resources.graphql_api import GraphQL
from pbench.common.logger import get_pbench_logger
from pbench.server.api.resources.query_apis.elasticsearch_api import Elasticsearch
from pbench.server.api.resources.query_apis.query_controllers import QueryControllers


def register_endpoints(api, app, config):
    """Register flask endpoints with the corresponding resource classes
    to make the APIs active."""

    base_uri = config.rest_uri
    app.logger.info("Registering service endpoints with base URI {}", base_uri)

    api.add_resource(
        Upload,
        f"{base_uri}/upload/ctrl/<string:controller>",
        resource_class_args=(config, app.logger),
    )
    api.add_resource(
        HostInfo, f"{base_uri}/host_info", resource_class_args=(config, app.logger),
    )
    api.add_resource(
        Elasticsearch,
        f"{base_uri}/elasticsearch",
        resource_class_args=(config, app.logger),
    )
    api.add_resource(
        GraphQL, f"{base_uri}/graphql", resource_class_args=(config, app.logger),
    )

    api.add_resource(
        QueryControllers,
        f"{base_uri}/controllers/list",
        resource_class_args=(config, app.logger),
    )


def get_server_config():
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        raise ConfigFileNotSpecified(
            f"{__name__}: ERROR: No config file specified; set" " _PBENCH_SERVER_CONFIG"
        )

    try:
        return PbenchServerConfig(cfg_name)
    except BadConfig as e:
        raise Exception(f"{__name__}: {e} (config file {cfg_name})").with_traceback(
            e.__traceback__
        )


def create_app(server_config):
    """Create Flask app with defined resource endpoints."""

    app = Flask("api-server")
    api = Api(app)

    app.logger = get_pbench_logger(__name__, server_config)

    app.config["DEBUG"] = False
    app.config["TESTING"] = False

    register_endpoints(api, app, server_config)

    return app
