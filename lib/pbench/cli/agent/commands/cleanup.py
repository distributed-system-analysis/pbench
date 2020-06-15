import sys

import click

from pbench.agent.logger import logger
from pbench.agent.utils.fs import rmtree
from pbench.agent.config import AgentConfig
from pbench.agent.utils import initialize
from pbench.cli import options


@click.command(
    help="clean up everything, including results and what tools" "have been registered"
)
@click.pass_context
@options.pbench_agent_config
def cleanup(debug, config):
    c = AgentConfig(config)

    # Initialize an environment
    initialize(c)

    try:
        (result, errors) = rmtree(c.rundir)
        if not result:
            logger.error("\n".join(errors))
        sys.exit(result)
    except Exception as ex:
        logger.error("Failed to remove %s: %s", c.rundir, ex)
