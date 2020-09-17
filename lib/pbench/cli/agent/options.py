import sys

import click

from pbench.agent import PbenchAgentConfig
from pbench.cli.agent import CliContext


def common_options(f):
    f = _pbench_agent_config(f)
    return f


def _pbench_agent_config(f):
    """Option for agent configuration"""

    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        try:
            if value is None:
                click.secho(f"Unable to load configuration file {value}", err="red")
                sys.exit(1)

            clictx.config = PbenchAgentConfig(value)
            return value
        except Exception as ex:
            click.secho(f"Failed to load {value}: {ex}")

        return value

    return click.option(
        "-C",
        "--config",
        envvar="_PBENCH_AGENT_CONFIG",
        type=click.Path(exists=True),
        callback=callback,
        expose_value=False,
        help=(
            "Path to a pbench-agent config. If provided pbench will load "
            "this config file first. By default is looking for config in "
            "'_PBENCH_AGENT_CONFIG' envrionment variable."
        ),
    )(f)
