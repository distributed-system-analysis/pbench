import os
import sys

import click

from pbench.cli.server import options
from pbench.cli.server import server


@click.command()
@click.pass_context
@options.server_config_option
@options.common_arguments
def config_activate(context, cfg_name, args):
    prog = os.path.basename(sys.argv[0])
    subcommand_args = {"config": cfg_name, "prog": prog, "args": args}
    server.PbenchServerCli(context, subcommand_args).main()
