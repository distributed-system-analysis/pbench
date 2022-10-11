"""pbench-register-tool-trigger

The sole purpose of this script is to register tool triggers for a given
tool group of your choosing.  During the execution of a benchmark, the
output of the benchmark is used to trigger the starting of tools and the
stopping of tools.
"""
import sys

import click

from pbench.agent.tool_group import (
    BadStartTrigger,
    BadStopTrigger,
    BadToolGroup,
    ToolGroup,
)
from pbench.cli.agent import BaseCommand, CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class TriggerRegister(BaseCommand):
    """Register tool trigger"""

    def __init__(self, context):
        super().__init__(context)

    def execute(self):
        try:
            tool_group = ToolGroup(self.context.group, self.pbench_run)
        except BadToolGroup as exc:
            click.echo(
                f'{self.name}: invalid --group option "{self.context.group}"'
                f" ({exc})",
                err=True,
            )
            return 1

        # Remember this trigger
        try:
            tool_group.store_trigger(self.context.start, self.context.stop)
        except BadStartTrigger:
            click.echo(
                f"{self.name}: the start trigger cannot have a colon in it:"
                f' "{self.context.start}"',
                err=True,
            )
            return 1
        except BadStopTrigger:
            click.echo(
                f"{self.name}: the stop trigger cannot have a colon in it:"
                f' "{self.context.stop}"',
                err=True,
            )
            return 1
        click.secho(
            f'tool trigger strings for start: "{self.context.start}"'
            f' and for stop: "{self.context.stop}" are now registered'
            f' for tool group: "{self.context.group}"'
        )

        return 0


def _group_option(f):
    """Group option"""

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


def _start_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.start = value
        return value

    return click.option(
        "--start-trigger",
        required=True,
        expose_value=False,
        callback=callback,
    )(f)


def _stop_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.stop = value
        return value

    return click.option(
        "--stop-trigger",
        required=True,
        expose_value=False,
        callback=callback,
    )(f)


@click.command(help="list registered triggers")
@common_options
@_group_option
@_start_option
@_stop_option
@pass_cli_context
def main(ctxt):
    status = TriggerRegister(ctxt).execute()
    sys.exit(status)
