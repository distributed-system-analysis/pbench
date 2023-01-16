from pbench.server import PbenchServerConfig
from pbench.server.database import init_db


def config_setup(context: object) -> PbenchServerConfig:
    config = PbenchServerConfig.create(context.config)
    # We're going to need the DB to track dataset state, so setup DB access.
    init_db(config, None)
    return config
