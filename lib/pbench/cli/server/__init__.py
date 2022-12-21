from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.globals import init_server_ctx


def config_setup(context: object, logger_name: str):
    config = PbenchServerConfig.create(context.config)
    logger = get_pbench_logger(logger_name, config)
    init_server_ctx(config, logger)
    # We're going to need the DB to track dataset state, so setup DB access.
    init_db()
