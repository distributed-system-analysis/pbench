# -*- mode: python -*-

"""pbench-tool-meister-stop

Responsible for stopping all local/remote tool meisters, closing down the data
sink, and finally the redis server.
"""

import sys

import click

from pbench.cli.agent import pass_cli_context
from pbench.agent.meister.base import MeisterCommand


class Stop(MeisterCommand):
    def __init__(self, context):
        super(Stop, self).__init__(context)

    def execute(self):
        return self.stop()


@click.command(help="")
@pass_cli_context
def main(ctxt):
    """Main program for the tool meister stop.

    This simply sends the "terminate" message to the redis server so that all
    connected services, tool-meisters, tool-data-sink, etc. will shutdown.
    Once all services acknowledge the receipt of the "terminate" message, we
    declare victory.

    TBD:

    We currently have a mode to "double-check" that the services all stopped
    by ssh'ing into all the local/remote hosts and inspecting the system for
    any lingering processes.
    """
    status = Stop(ctxt).execute()
    sys.exit(status)
