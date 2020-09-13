import os
import sys

import click

from pbench.agent.tools.base import ToolCommand
from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class Clear(ToolCommand):
    def __init__(self, context):
        super(Clear, self).__init__(context)

        self.logger = setup_logging(name=os.path.basename(sys.argv[0]), logfile=self.pbench_log)

    def execute(self):
        return self.clear_tools()


def _group_option(f):
    """Pbench noinstall option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.group = value
        return value

    return click.option(
        "-g",
        "--groups",
        "--group",
        default="default",
        expose_value=False,
        callback=callback,
    )(f)


def _name_option(f):
    """Pbench noinstall option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.name = []
        if value:
            clictxt.name.append(value)
        return value

    return click.option(
        "-n", "--names", "--name", expose_value=False, callback=callback,
    )(f)


def _remotes_option(f):
    """Pbench noinstall option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        try:
            clictxt.remotes = value.split(",") if "," in value else [value]
        except Exception:
            clictxt.remotes = []
        return value

    return click.option(
        "-r", "--remotes", "--remote", expose_value=False, callback=callback,
    )(f)



@click.command(help="")
@common_options
@_name_option
@_group_option
@_remotes_option
@pass_cli_context
def main(ctxt):
    status = Clear(ctxt).execute()
    sys.exit(status)
