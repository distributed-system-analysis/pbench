from pathlib import Path
import shutil
import sys

import click

from pbench.agent.logger import logger
from pbench.agent.config import AgentConfig
from pbench.agent.utils import initialize
from pbench.cli import options


@click.group(help="agent administrative commands")
@click.pass_context
def config(ctxt):
    """Place holder for pbench-cli config subcomand"""
    pass


@click.command(help="copy the configuration file to the destination")
@options.pbench_agent_config
# do not use the agent default ere becore the configuration should
# not exist at this point
@click.pass_context
@click.argument("config", type=click.Path(exists=True))
def activate(debug, config):
    c = AgentConfig(config)

    # Initialize an environment
    initialize(c)
    try:
        src = Path(config)
        dest = Path(c.installdir, "config/pbench-agent.cfg")

        if not dest.exists():
            try:
                shutil.copy(src, dest)
            except Exception as ex:
                logger.error("Failed to copy %s: %s", src, ex)
                sys.exit(1)
    except Exception as ex:
        logger.error("Failed copy %s: %s", src, ex)
        sys.exit(1)


@click.command(help="copy ssh key file")
@click.pass_context
@click.argument("config", type=click.Path(exists=True))
@click.argument("keyfile", type=click.Path(exists=True))
def ssh(debug, config, keyfile):
    c = AgentConfig(config)

    # Initialize an environment
    initialize(c)

    try:
        src = Path(keyfile)
        dest = Path(c.installdir, "id_rsa")

        if not dest.exists():
            try:
                shutil.copy(src, dest)
            except Exception as ex:
                logger.error("Failed to copy ssh key %s: %s", src, ex)
                sys.exit(1)
    except Exception as ex:
        logger.error("Failed copy ssh key %s: %s", src, ex)
        sys.exit(1)


config.add_command(activate)
config.add_command(ssh)
