import os
import sys

import click

from pbench.agent.triggers.base import TriggerCommand
from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options

NAME = os.path.basename(sys.argv[0])


class Register(TriggerCommand):
    def __init__(self, context):
        super(Register, self).__init__(context)
        
    def execute(self):
        return self.register()

def _group_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.group = value
        return value

    return click.option(
        "-g", "--groups", "--group", default="default", expose_value=False, callback=callback,
    )(f)


def _start_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        if ":" in value:
            click.secho(f'{NAME}: the start trigger cannot have a colon in it: \"{value}\"')
            sys.exit(1)
        clictxt.start = value
        return value

    return click.option(
        "--start-trigger", required=True, expose_value=False, callback=callback,
    )(f)


def _stop_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        if ":" in value:
            click.secho(f'{NAME}: the stop trigger cannot have a colon in it: \"{value}\"')
            sys.exit(1)
        clictxt.stop = value
        return value

    return click.option(
        "--stop-trigger", required=True, expose_value=False, callback=callback,
    )(f)

@click.command(help="")
@common_options
@_group_option
@_start_option
@_stop_option
@pass_cli_context
def main(ctxt):
    status = Register(ctxt).execute()
    sys.exit(status)