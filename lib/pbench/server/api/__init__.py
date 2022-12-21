"""Pbench Server API module

Provides middleware for remote clients, either the associated Pbench Dashboard
or any number of pbench agent users.
"""

import os

from flask import current_app, Flask
from flask_cors import CORS
from flask_restful import Api

from pbench.common.exceptions import ConfigFileNotSpecified
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
from pbench.server.api.resources.query_apis.datasets_search import DatasetsSearch
from pbench.server.api.resources.query_apis.datasets_update import DatasetsUpdate
from pbench.server.api.resources.server_audit import ServerAudit
from pbench.server.api.resources.server_settings import ServerSettings
from pbench.server.api.resources.upload_api import Upload
from pbench.server.api.resources.users_api import Login, Logout, RegisterUser, UserAPI
import pbench.server.auth.auth as Auth
from pbench.server.database import init_db
from pbench.server.globals import init_server_ctx, server


def register_endpoints():
    """Register flask endpoints with the corresponding resource classes
    to make the APIs active.
    """

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
        DatasetsSearch,
        DatasetsUpdate,
        EndpointConfig,
        Login,
        Logout,
        RegisterUser,
        SampleNamespace,
        SampleValues,
        ServerAudit,
        ServerSettings,
        Upload,
        UserAPI,
    ]:
        urls = [f"{server.config.rest_uri}/{url}" for url in kls.urls]
        api.add_resource(kls, *urls, endpoint=kls.endpoint)


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
    logger = get_pbench_logger(__name__, server_config)
    init_server_ctx(server_config, logger)

    def shutdown_session(exception=None):
        """Called from app context teardown hook to end the database session"""
        server.db_session.remove()

    app = Flask(__name__.split(".")[0])
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    with app.app_context():
        Auth.setup_app(app)
        register_endpoints()
        init_db()

    app.teardown_appcontext(shutdown_session)

    return app
