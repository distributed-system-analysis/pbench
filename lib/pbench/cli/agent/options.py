import os
import click


class CliContext:
    def __init__(self):
        self.config = None

    def initialize(self):
        pass


pass_cli_context = click.make_pass_decorator(CliContext, ensure=True)


#
# Agent options
#
def pbench_upload_user(f):
    return click.option(
        "-u", "--user", "user", default="", help="Specify username for server upload"
    )(f)


def pbench_server_prefix(f):
    return click.option(
        "-p", "--prefix", default="", help="Specify a prefix for server upload"
    )(f)


def pbench_show_server(f):
    return click.option("-S", "--show-server", required=False, help="Show server",)(f)


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
