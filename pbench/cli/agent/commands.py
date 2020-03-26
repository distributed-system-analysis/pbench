import os

import click

from pbench.cli.agent.cleanup import PbenchCleanup
from pbench.cli.agent.setup import PbenchConfigure, PbenchSSHKey
from pbench.cli.agent.tools import PbenchCleanupTools
from pbench.common.utils import sysexit


@click.command()
def cleanup():
    PbenchCleanup().main()


@click.command()
@click.argument("cfg_file", nargs=1)
def setup_config(cfg_file):
    if not os.path.exists(cfg_file):
        print("{} does not exist".format(cfg_file))
        sysexit()
    PbenchConfigure(cfg_file).main()


@click.command()
@click.argument("cfg_file", nargs=1)
@click.argument("keyfile", nargs=1)
def setup_ssh_key(cfg_file, keyfile):
    command_args = {"keyfile": keyfile}
    PbenchSSHKey(cfg_file, command_args).main()


@click.command()
def clear_results():
    PbenchCleanupTools().main()


@click.command()
@click.option(
    "-g", "--group", "group", help="The group from which tools should be removed",
)
@click.option(
    "-n",
    "--name",
    "name",
    help="a specific tool to be removed. If no tool is specified, all "
    "tools in the group are removed",
)
def clear_tools(group, name):
    command_args = {"group": group, "name": name}
    PbenchCleanupTools(None, command_args).main()
