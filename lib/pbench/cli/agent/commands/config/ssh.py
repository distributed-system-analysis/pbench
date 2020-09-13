import os
import sys

import click

from pbench.agent import PbenchAgentConfig
from pbench.agent.config.base import ConfigCommand
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class SSH(ConfigCommand):
    def __init__(self, context):
        super(SSH, self).__init__(context)

    def execute(self):
        return self.ssh()

def _config_option(f):
    """Option for agent configuration"""

    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        try:
            if value is None or not os.path.exists(value):
                click.secho(f"Configuration file is not found: {value}", err="Red")
                sys.exit(1)

            clictx.config = PbenchAgentConfig(value)
        except Exception as ex:
            click.secho(f"Failed to load {value}: {ex}", err="red")
            sys.exit(1)

    return click.argument(
        "config", expose_value=False, type=click.Path(exists=True), callback=callback
    )(f)

def _key_file(f):
    """Option for ssh key file"""

    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.ssh_key = value
        return value

    return click.argument(
        "ssh_key", expose_value=False, type=click.Path(exists=True), callback=callback
    )(f)

@click.command(help="")
@common_options
@_config_option
@_key_file
@pass_cli_context
def main(ctxt):
    status = SSH(ctxt).execute()
    sys.exit(status)
