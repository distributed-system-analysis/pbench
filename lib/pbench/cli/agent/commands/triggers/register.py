"""
pbench-register-tool-trigger

The sole purpose of this script is to register tool triggers for a given
tool group of your choosing.  During the execution of a benchmark, the
output of the benchmark is used to trigger the starting of tools and the
stopping of tools.

For a list of performance tools, look at the ${pbench_bin}/tool-scripts
directory.

"""
import logging
import sys

import click

from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.commands.triggers.base import TriggerCommand
from pbench.cli.agent.options import common_options

LOG = logging.getLogger(__name__)


class TriggerRegister(TriggerCommand):
    """Register tool trigger"""

    def __init__(self, context):
        super().__init__(context)

        setup_logging(debug=False, logfile=None)

    def execute(self):
        if self.verify_tool_group(self.context.group) != 0:
            return 1

        if ":" in self.context.start:
            LOG.error(
                '%s: the start trigger cannot have a colon in it: "%s"',
                self.name,
                self.context.start,
            )
            return 1

        if ":" in self.context.stop:
            LOG.error(
                '%s: the stop trigger cannot have a colon in it: "%s"',
                self.name,
                self.context.stop,
            )
            return 1

        # Remember this trigger
        trigger = self.tool_group_dir / "__trigger__"
        trigger.write_text(f"{self.context.start}:{self.context.stop}\n")
        click.secho(
            f'tool trigger strings for start: "{self.context.start}" and for stop: "{self.context.stop}" are now registered for tool group: "{self.context.group}"'
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
        "--start-trigger", required=True, expose_value=False, callback=callback,
    )(f)


def _stop_option(f):
    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.stop = value
        return value

    return click.option(
        "--stop-trigger", required=True, expose_value=False, callback=callback,
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
