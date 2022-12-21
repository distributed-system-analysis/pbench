"""
Pbench Server API module -
Provides middleware for remote clients, either the associated Pbench
Dashboard or any number of pbench agent users.
"""

import os
import sys

from flask import current_app, Flask
from flask_cors import CORS
from flask_restful import Api

from pbench.common.exceptions import BadConfig, ConfigFileNotSpecified
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.api.resources.datasets_daterange import DatasetsDateRange
from pbench.server.api.resources.datasets_inventory import DatasetsInventory
from pbench.server.api.resources.datasets_list import DatasetsList
from pbench.server.api.resources.datasets_metadata import DatasetsMetadata
from pbench.server.api.resources.endpoint_configure import EndpointConfig
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
from pbench.server.api.resources.query_apis.datasets_delete import DatasetsDelete
from pbench.server.api.resources.query_apis.datasets_publish import DatasetsPublish
from pbench.server.api.resources.query_apis.datasets_search import DatasetsSearch
from pbench.server.api.resources.server_audit import ServerAudit
from pbench.server.api.resources.server_configuration import ServerConfiguration
from pbench.server.api.resources.upload_api import Upload
from pbench.server.api.resources.users_api import Login, Logout, RegisterUser, UserAPI
from pbench.server.auth import auth
from pbench.server.database import init_db
from pbench.server.globals import init_server_ctx, server


def register_endpoints():
    """Register flask endpoints with the corresponding resource classes
    to make the APIs active."""

    server.logger.info(
        "Registering service endpoints with base URI {}", server.config.rest_uri
    )
    api = Api(current_app)
    for kls in [
        DatasetsContents,
        DatasetsDateRange,
        DatasetsDelete,
        DatasetsDetail,
        DatasetsInventory,
        DatasetsList,
        DatasetsMappings,
        DatasetsMetadata,
        DatasetsPublish,
        DatasetsSearch,
        EndpointConfig,
        Login,
        Logout,
        RegisterUser,
        SampleNamespace,
        SampleValues,
        ServerAudit,
        ServerConfiguration,
        Upload,
        UserAPI,
    ]:
        urls = [f"{server.config.rest_uri}/{url}" for url in kls.urls]
        api.add_resource(kls, *urls, endpoint=kls.endpoint)


def get_server_config() -> PbenchServerConfig:
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        raise ConfigFileNotSpecified(
            f"{__name__}: ERROR: No config file specified; set _PBENCH_SERVER_CONFIG"
        )

    try:
        return PbenchServerConfig(cfg_name)
    except BadConfig as e:
        raise Exception(f"{__name__}: {e} (config file {cfg_name})").with_traceback(
            e.__traceback__
        )


def create_app(config: PbenchServerConfig):
    """Create Flask app with defined resource endpoints."""
    logger = get_pbench_logger(__name__, config)
    init_server_ctx(config, logger)

    app = Flask("api-server")
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    with app.app_context():
        auth.setup_app()
        register_endpoints()
        try:
            init_db()
        except Exception:
            logger.exception("Exception while initializing sqlalchemy database")
            sys.exit(1)

        @app.teardown_appcontext
        def shutdown_session(exception=None):
            server.db_session.remove()

    return app
