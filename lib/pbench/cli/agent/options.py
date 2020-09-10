import os
import click


#
# Default options
#
def pbench_agent_config(f):
    """Option for agent configuration"""
    return click.option(
        "-C",
        "--config",
        default=os.environ.get("_PBENCH_AGENT_CONFIG"),
        help=(
            "Path to a pbench-agent config. If provided pbench will load "
            "this config file first. By default is looking for config in "
            "'_PBENCH_AGENT_CONFIG' envrionment variable."
        ),
    )(f)


def pbench_agent_debug(f):
    """Turn on/off debug"""
    return click.option(
        "--debug",
        default=False,
        help="Enable or disable debug mode. Default is disabled",
    )(f)
