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
from pbench.server.database import init_db
from pbench.server.globals import init_server_ctx


class CliContext:
    """Initialize an empty click object"""

    pass


pass_cli_context = click.make_pass_decorator(CliContext, ensure=True)


def config_setup(context: object, logger_name: str):
    config = PbenchServerConfig(context.config)
    logger = get_pbench_logger(logger_name, config)
    init_server_ctx(config, logger)
    # We're going to need the DB to track dataset state, so setup DB access.
    init_db()
