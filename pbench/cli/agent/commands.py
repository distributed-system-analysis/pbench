import os

import click

from pbench.cli.agent.cleanup import PbenchCleanup, PbenchCleanupTools
from pbench.cli.agent.setup import PbenchConfigure, PbenchSSHKey
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
