from pbench.server import get_pbench_server_config, PbenchServerConfig
from pbench.server.database import init_db


def config_setup(context: object) -> PbenchServerConfig:
    config = get_pbench_server_config(context.config)
    # We're going to need the DB to track dataset state, so setup DB access.
    init_db(config, None)
    return config
