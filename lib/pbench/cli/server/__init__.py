"""
Create a click context object that holds the state of the server
invocation. The CliContext will keep track of passed parameters,
what command created it, which resources need to be cleaned up,
and etc.

We create an empty object at the beginning and populate the object
with configuration, group names, at the beginning of the server
execution.
"""

import click
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database.database import Database


class CliContext:
    """Initialize an empty click object"""

    pass


pass_cli_context = click.make_pass_decorator(CliContext, ensure=True)


def config_setup(context: object, name: str) -> None:
    config = PbenchServerConfig(context.config)
    logger = get_pbench_logger(name, config)

    # We're going to need the Postgres DB to track dataset state, so setup
    # DB access.
    try:
        if not Database.db_session:
            Database.init_db(config, logger)
    except Exception:
        Database.init_db(config, logger)
