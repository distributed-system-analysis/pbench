"""
Pbench Server API module -
Provides middleware for remote clients, either the associated Pbench
Dashboard or any number of pbench agent users.
"""

import os
import sys

from flask import Flask
from flask_cors import CORS
from flask_restful import Api

from pbench.common.exceptions import BadConfig, ConfigFileNotSpecified
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.api.resources.datasets_daterange import DatasetsDateRange
from pbench.server.api.resources.datasets_list import DatasetsList
from pbench.server.api.resources.datasets_metadata import DatasetsMetadata
from pbench.server.api.resources.datasets_inventory import DatasetsInventory
from pbench.server.api.resources.endpoint_configure import EndpointConfig
from pbench.server.api.resources.graphql_api import GraphQL
from pbench.server.api.resources.query_apis.datasets.datasets_contents import (
    DatasetsContents,
)
from pbench.server.api.resources.query_apis.datasets.datasets_mappings import (
    DatasetsMappings,
)
from pbench.server.api.resources.query_apis.datasets.namespace_and_rows import (
    SampleNamespace,
    SampleValues,
)
from pbench.server.api.resources.query_apis.datasets_delete import DatasetsDelete
from pbench.server.api.resources.query_apis.datasets_detail import DatasetsDetail
from pbench.server.api.resources.query_apis.datasets_publish import DatasetsPublish
from pbench.server.api.resources.query_apis.datasets_search import DatasetsSearch
from pbench.server.api.resources.query_apis.elasticsearch_api import Elasticsearch
from pbench.server.api.resources.server_configuration import ServerConfiguration
from pbench.server.api.resources.upload_api import Upload
from pbench.server.api.resources.users_api import Login, Logout, RegisterUser, UserAPI
from pbench.server.database import init_db
from pbench.server.database.database import Database


def register_endpoints(api, app, config):
    """Register flask endpoints with the corresponding resource classes
    to make the APIs active."""

    base_uri = config.rest_uri
    logger = app.logger

    # Init the the authentication module
    token_auth = Auth()
    Auth.set_logger(logger)

    logger.info("Registering service endpoints with base URI {}", base_uri)

    api.add_resource(
        DatasetsContents,
        f"{base_uri}/datasets/contents/<string:dataset>",
        endpoint="datasets_contents",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsDateRange,
        f"{base_uri}/datasets/daterange",
        endpoint="datasets_daterange",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsDelete,
        f"{base_uri}/datasets/delete/<string:dataset>",
        endpoint="datasets_delete",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsDetail,
        f"{base_uri}/datasets/detail/<string:dataset>",
        endpoint="datasets_detail",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsList,
        f"{base_uri}/datasets/list",
        endpoint="datasets_list",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsMappings,
        f"{base_uri}/datasets/mappings/<string:dataset_view>",
        endpoint="datasets_mappings",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsMetadata,
        f"{base_uri}/datasets/metadata/<string:dataset>",
        endpoint="datasets_metadata",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsInventory,
        f"{base_uri}/datasets/inventory/<string:dataset>/<path:path>",
        endpoint="datasets_inventory",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        SampleNamespace,
        f"{base_uri}/datasets/namespace/<string:dataset_view>",
        endpoint="datasets_namespace",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        SampleValues,
        f"{base_uri}/datasets/values/<string:dataset_view>",
        endpoint="datasets_values",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsPublish,
        f"{base_uri}/datasets/publish/<string:dataset>",
        endpoint="datasets_publish",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        DatasetsSearch,
        f"{base_uri}/datasets/search",
        endpoint="datasets_search",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        Elasticsearch,
        f"{base_uri}/elasticsearch",
        endpoint="elasticsearch",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        EndpointConfig,
        f"{base_uri}/endpoints",
        endpoint="endpoints",
        resource_class_args=(config, logger),
    )

    api.add_resource(
        GraphQL,
        f"{base_uri}/graphql",
        endpoint="graphql",
        resource_class_args=(config, logger),
    )

    api.add_resource(
        Login,
        f"{base_uri}/login",
        endpoint="login",
        resource_class_args=(config, logger, token_auth),
    )
    api.add_resource(
        Logout,
        f"{base_uri}/logout",
        endpoint="logout",
        resource_class_args=(config, logger, token_auth),
    )
    api.add_resource(
        RegisterUser,
        f"{base_uri}/register",
        endpoint="register",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        ServerConfiguration,
        f"{base_uri}/server/configuration",
        f"{base_uri}/server/configuration/",
        f"{base_uri}/server/configuration/<string:key>",
        endpoint="server_configuration",
        resource_class_args=(config, logger),
    )
    api.add_resource(
        UserAPI,
        f"{base_uri}/user/<string:target_username>",
        endpoint="user",
        resource_class_args=(logger, token_auth),
    )
    api.add_resource(
        Upload,
        f"{base_uri}/upload/<string:filename>",
        endpoint="upload",
        resource_class_args=(config, logger),
    )


def get_server_config() -> PbenchServerConfig:
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
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.logger = get_pbench_logger(__name__, server_config)

    app.config["DEBUG"] = False
    app.config["TESTING"] = False

    api = Api(app)

    register_endpoints(api, app, server_config)

    try:
        init_db(server_config=server_config, logger=app.logger)
    except Exception:
        app.logger.exception("Exception while initializing sqlalchemy database")
        sys.exit(1)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        Database.db_session.remove()

    return app
