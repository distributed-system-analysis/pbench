"""Pbench Server API module

Provides middleware for remote clients, either the associated Pbench Dashboard
or any number of pbench agent users.
"""

import os

from flask import Flask
from flask_cors import CORS
from flask_restful import Api

from pbench.common.exceptions import ConfigFileNotSpecified
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.api.resources.api_key import APIKey
from pbench.server.api.resources.datasets_inventory import DatasetsInventory
from pbench.server.api.resources.datasets_list import DatasetsList
from pbench.server.api.resources.datasets_metadata import DatasetsMetadata
from pbench.server.api.resources.endpoint_configure import EndpointConfig
from pbench.server.api.resources.query_apis.dataset import Datasets
from pbench.server.api.resources.query_apis.datasets.datasets_contents import (
    DatasetsContents,
)
from pbench.server.api.resources.query_apis.datasets.datasets_detail import (
    DatasetsDetail,
)
from pbench.server.api.resources.query_apis.datasets.datasets_mappings import (
    DatasetsMappings,
)
from pbench.server.api.resources.query_apis.datasets.namespace_and_rows import (
    SampleNamespace,
    SampleValues,
)
from pbench.server.api.resources.query_apis.datasets_search import DatasetsSearch
from pbench.server.api.resources.server_audit import ServerAudit
from pbench.server.api.resources.server_settings import ServerSettings
from pbench.server.api.resources.upload_api import Upload
import pbench.server.auth.auth as Auth
from pbench.server.database import init_db
from pbench.server.database.database import Database


def register_endpoints(api: Api, app: Flask, config: PbenchServerConfig):
    """Register flask endpoints with the corresponding resource classes
    to make the APIs active.

    Args:
        api : the Flask Api object with which to register the end points
        app : the Flask application in use
        config : the Pbench server configuration object in use
    """

    base_uri = config.rest_uri

    app.logger.info("Registering service endpoints with base URI {}", base_uri)

    api.add_resource(
        Datasets,
        f"{base_uri}/datasets/<string:dataset>",
        endpoint="datasets",
        resource_class_args=(config,),
    )
    api.add_resource(
        DatasetsContents,
        f"{base_uri}/datasets/<string:dataset>/contents/",
        f"{base_uri}/datasets/<string:dataset>/contents/<path:target>",
        endpoint="datasets_contents",
        resource_class_args=(config,),
    )
    api.add_resource(
        DatasetsDetail,
        f"{base_uri}/datasets/<string:dataset>/detail",
        endpoint="datasets_detail",
        resource_class_args=(config,),
    )
    api.add_resource(
        DatasetsList,
        f"{base_uri}/datasets",
        endpoint="datasets_list",
        resource_class_args=(config,),
    )
    api.add_resource(
        DatasetsMappings,
        f"{base_uri}/datasets/mappings/<string:dataset_view>",
        endpoint="datasets_mappings",
        resource_class_args=(config,),
    )
    api.add_resource(
        DatasetsMetadata,
        f"{base_uri}/datasets/<string:dataset>/metadata",
        endpoint="datasets_metadata",
        resource_class_args=(config,),
    )
    api.add_resource(
        DatasetsInventory,
        f"{base_uri}/datasets/<string:dataset>/inventory",
        f"{base_uri}/datasets/<string:dataset>/inventory/",
        f"{base_uri}/datasets/<string:dataset>/inventory/<path:target>",
        endpoint="datasets_inventory",
        resource_class_args=(config,),
    )
    api.add_resource(
        SampleNamespace,
        f"{base_uri}/datasets/<string:dataset>/namespace/<string:dataset_view>",
        endpoint="datasets_namespace",
        resource_class_args=(config,),
    )
    api.add_resource(
        SampleValues,
        f"{base_uri}/datasets/<string:dataset>/values/<string:dataset_view>",
        endpoint="datasets_values",
        resource_class_args=(config,),
    )
    api.add_resource(
        DatasetsSearch,
        f"{base_uri}/datasets/search",
        endpoint="datasets_search",
        resource_class_args=(config,),
    )
    api.add_resource(
        EndpointConfig,
        f"{base_uri}/endpoints",
        endpoint="endpoints",
        resource_class_args=(config,),
    )
    api.add_resource(
        APIKey,
        f"{base_uri}/key",
        endpoint="key",
        resource_class_args=(config,),
    )
    api.add_resource(
        ServerAudit,
        f"{base_uri}/server/audit",
        endpoint="server_audit",
        resource_class_args=(config,),
    )
    api.add_resource(
        ServerSettings,
        f"{base_uri}/server/settings",
        f"{base_uri}/server/settings/",
        f"{base_uri}/server/settings/<string:key>",
        endpoint="server_settings",
        resource_class_args=(config,),
    )
    api.add_resource(
        Upload,
        f"{base_uri}/upload/<string:filename>",
        endpoint="upload",
        resource_class_args=(config,),
    )


def get_server_config() -> PbenchServerConfig:
    """Get a pbench server configuration object

    The file to use for the configuration is specifed by the environment
    variable, `_PBENCH_SERVER_CONFIG`.

    Raises:
        ConfigFileNotSpecified : when no value is given for the environment
            variable

    Returns:
        A PbenchServerConfig object
    """
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        raise ConfigFileNotSpecified(
            f"{__name__}: ERROR: No config file specified; set _PBENCH_SERVER_CONFIG"
        )

    return PbenchServerConfig.create(cfg_name)


def create_app(server_config: PbenchServerConfig) -> Flask:
    """Create Flask app with defined resource endpoints.

    Args:
        server_config: A pbench server configuration object

    Returns:
        A Flask application object on success
    """

    def shutdown_session(exception=None):
        """Called from app context teardown hook to end the database session"""
        Database.db_session.remove()

    app = Flask(__name__.split(".")[0])
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.logger = get_pbench_logger(__name__, server_config)

    Auth.setup_app(app, server_config)

    api = Api(app)

    with app.app_context():
        register_endpoints(api, app, server_config)

    try:
        init_db(configuration=server_config, logger=app.logger)
    except Exception:
        app.logger.exception("Exception while initializing sqlalchemy database")
        raise

    app.teardown_appcontext(shutdown_session)

    return app
