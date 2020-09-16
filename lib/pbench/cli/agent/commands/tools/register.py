import os
import socket
import sys

import click

from pbench.agent.tools.base import ToolCommand
from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class Register(ToolCommand):
    def __init__(self, context):
        super(Register, self).__init__(context)

        self.logger = setup_logging(
            name=os.path.basename(sys.argv[0]), logfile=self.pbench_log
        )

    def execute(self):
        return self.register_tool()


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
        clictxt.name = value
        return value

    return click.option(
        "-n", "--names", "--name", required=True, expose_value=False, callback=callback,
    )(f)


def _labels_option(f):
    """Pbench labels option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.labels_arg = value
        return value

    return click.option("--labels", expose_value=False, callback=callback,)(f)


def _remotes_option(f):
    """Pbench noinstall option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.remotes_arg = value
        return value

    if os.environ.get("_PBENCH_UNIT_TESTS"):
        hostname = "testhost.example.com"
    else:
        hostname = socket.gethostname()

    return click.option(
        "-r",
        "--remotes",
        "--remote",
        default=hostname,
        expose_value=False,
        callback=callback,
    )(f)


def _noinstall_option(f):
    """Pbench noinstall option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.noinstall = value
        return value

    return click.option(
        "--no-install",
        expose_value=False,
        is_flag=True,
        default=False,
        callback=callback,
    )(f)


def _testlabel_option(f):
    """Pbench noinstall option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.testlabel = value
        return value

    return click.option(
        "--test-labels",
        expose_value=False,
        is_flag=True,
        default=False,
        callback=callback,
    )(f)


def _toolopts_option(f):
    """Pbench toolopts option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.tool_opts = value
        return value

    return click.argument(
        "tools_opts", nargs=-1, expose_value=False, callback=callback, required=False,
    )(f)


@click.command(help="")
@common_options
@_name_option
@_group_option
@_labels_option
@_remotes_option
@_noinstall_option
@_testlabel_option
@_toolopts_option
@pass_cli_context
def main(ctxt):
    status = Register(ctxt).execute()
    sys.exit(status)
