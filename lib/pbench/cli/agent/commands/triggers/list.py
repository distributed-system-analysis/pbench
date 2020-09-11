import os
import sys

import click

from pbench.agent.triggers.base import TriggerCommand
from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class List(TriggerCommand):
    def __init__(self, context):
        super(List, self).__init__(context)

        self.logger = setup_logging(name=os.path.basename(sys.argv[0]), logfile=self.pbench_log)

    def execute(self):
        return self.list()

def _group_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.group = value
        return value

    return click.option(
        "-g", "--groups", "--group", expose_value=False, callback=callback,
    )(f)

@click.command(help="")
@common_options
@_group_option
@pass_cli_context
def main(ctxt):
    status = List(ctxt).execute()
    sys.exit(status)
