import os
import sys

import click

from pbench.agent.sysinfo.base import SysinfoCommand
from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class Collect(SysinfoCommand):
    def __init__(self, context):
        super(Collect, self).__init__(context)

        self.NAME = os.path.basename(sys.argv[0])
        self.logger = setup_logging(name=self.NAME, logfile=self.pbench_log)

    def execute(self):
        return self.collect()


def _group_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.group = value
        return value

    return click.option(
        "-g", "--group", default="default", expose_value=False, callback=callback,
    )(f)


def _dir_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.dir = value
        return value

    return click.option(
        "-d",
        "--dir",
        required=False,
        type=click.Path(),
        expose_value=False,
        callback=callback,
    )(f)


def _sysinfo_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.sysinfo = value
        return value

    return click.option(
        "--sysinfo",
        required=False,
        default="default",
        expose_value=False,
        callback=callback,
    )(f)


def _check_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.check = value
        return value

    return click.option(
        "--check", is_flag=True, expose_value=False, callback=callback,
    )(f)


def _options(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.options = value
        return value

    return click.option(
        "--options", is_flag=True, expose_value=False, callback=callback,
    )(f)


def _name_argument(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.name = value
        return value

    return click.argument(
        "name", required=False, expose_value=False, callback=callback,
    )(f)


@click.command(help="")
@common_options
@_group_option
@_dir_option
@_options
@_sysinfo_option
@_check_option
@_name_argument
@pass_cli_context
def main(ctxt):
    status = Collect(ctxt).execute()
    sys.exit(status)
