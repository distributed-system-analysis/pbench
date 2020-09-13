import os
import sys

import click

from pbench.agent import PbenchAgentConfig
from pbench.agent.config.base import ConfigCommand
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class Config(ConfigCommand):
    def __init__(self, context):
        super(Config, self).__init__(context)

    def execute(self):
        return self.config_activate()

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



@click.command(help="")
@common_options
@_config_option
@pass_cli_context
def main(ctxt):
    status = Config(ctxt).execute()
    sys.exit(status)
