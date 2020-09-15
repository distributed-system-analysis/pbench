import os
import sys

import click

from pbench.agent.tools.base import ToolCommand
from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class List(ToolCommand):
    def __init__(self, context):
        super(List, self).__init__(context)

        self.logger = setup_logging(
            name=os.path.basename(sys.argv[0]), logfile=self.pbench_log
        )

        if self.context.group and self.context.name:
            click.secho("You cannot specify both --group and --name", fg="red")
            sys.exit(1)

    def execute(self):
        return self.list_tools()


def _group_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        try:
            clictxt.group = value.split()
        except Exception:
            clictxt.group = []
        return value

    return click.option(
        "-g", "--groups", "--group", expose_value=False, callback=callback,
    )(f)


def _name_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.name = value
        return value

    return click.option(
        "-n", "--names", "--name", expose_value=False, callback=callback,
    )(f)


@click.command(help="")
@common_options
@_group_option
@_name_option
@pass_cli_context
def main(ctxt):
    status = List(ctxt).execute()
    sys.exit(status)
