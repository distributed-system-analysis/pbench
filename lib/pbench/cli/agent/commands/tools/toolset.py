from configparser import NoOptionError, NoSectionError
import os
import sys

import click

from pbench.agent.tools.base import ToolCommand
from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class ToolSet(ToolCommand):
    def __init__(self, context):
        super(ToolSet, self).__init__(context)

        self.logger = setup_logging(
            name=os.path.basename(sys.argv[0]), logfile=self.pbench_log
        )

        try:
            self.default_interval = self.config.get("pbench/tools", "interval")
        except (NoSectionError, NoOptionError):
            self.default_interval = self.context.interval

    def execute(self):
        return self.toolset()


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


def _labels_option(f):
    """Pbench labels option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.labels_arg = value
        return value

    return click.option("--labels", default="", expose_value=False, callback=callback,)(
        f
    )


def _remotes_option(f):
    """Pbench noinstall option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.remotes_arg = value
        return value

    return click.option(
        "-r",
        "--remotes",
        "--remote",
        default="",
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


def _interval_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.interval = value
        return value

    return click.option(
        "--interval",
        "-i",
        expose_value=False,
        required=True,
        default="3",
        callback=callback,
    )(f)


def _toolset_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.toolset = value
        return value

    return click.option(
        "--toolset",
        "-t",
        default="default",
        expose_value=False,
        required=True,
        callback=callback,
    )(f)


@click.command(help="")
@common_options
@_group_option
@_labels_option
@_remotes_option
@_noinstall_option
@_interval_option
@_toolset_option
@pass_cli_context
def main(ctxt):
    status = ToolSet(ctxt).execute()
    sys.exit(status)
