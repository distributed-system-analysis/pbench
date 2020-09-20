import os
import sys

import click

from pbench.agent.utils import setup_logging
from pbench.agent.tools.base import ToolCommand
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class PostProcess(ToolCommand):
    def __init__(self, context):
        super(PostProcess, self).__init__(context)

        self.NAME = os.path.basename(sys.argv[0])
        self.logger = setup_logging(name=self.NAME, logfile=self.pbench_log)

    def execute(self):
        return self.process()


def group_option(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.group = value
        return value

    return click.option(
        "-g",
        "--group",
        default="default",
        required=True,
        callback=callback,
        expose_value=False,
    )(f)


def directory_option(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.directory = value
        return value

    return click.option(
        "-d", "--dir", required=True, callback=callback, expose_value=False,
    )(f)


@click.command(help="")
@common_options
@group_option
@directory_option
@pass_cli_context
def main(ctxt):
    status = PostProcess(ctxt).execute()
    sys.exit(status)
