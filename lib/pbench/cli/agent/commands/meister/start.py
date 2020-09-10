# -*- mode: python -*-

"""pbench-tool-meister-start

Responsible for:

   1. Starting a redis server
   2. Loading tool group data for the given tool group into the redis server
   3. Starting the tool-data-sink process
   4. Starting all the local and remote tool meisters

When complete we leave running, locally, a redis server and a tool data sink
process, and any local or remote tool meisters.

The pbench-tool-meister-stop script will take care of (gracefully) stopping
all of these processes, locally or remotely.
"""

import sys

import click

from pbench.agent.meister.base import MeisterCommand
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class Start(MeisterCommand):
    def __init__(self, context):
        super(Start, self).__init__(context)

    def execute(self):
        return self.start()


def group_option(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.group = value
        return value

    return click.argument(
        "group",
        default="default",
        required=True,
        callback=callback,
        expose_value=False,
    )(f)


@click.command(help="")
@common_options
@group_option
@pass_cli_context
def main(ctxt):
    """Main program for the tool meister start.
    """
    status = Start(ctxt).execute()
    sys.exit(status)
