"""
pbench-list-triggers

This script will list all tool triggers from all tool groups, or list tool
triggers from a specific group.

"""
import sys

import click

from pbench.agent.tool_group import BadToolGroup, ToolGroup
from pbench.cli.agent import BaseCommand, CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class TriggerList(BaseCommand):
    """List register triggers"""

    def __init__(self, context):
        super().__init__(context)

    def execute(self):
        if not self.context.group:
            # list tool triggers in all groups
            for tool_group in ToolGroup.gen_tool_groups(self.pbench_run):
                trigger = tool_group.trigger()
                if trigger:
                    print(f"{tool_group.name}: {trigger}")
        else:
            # list tool triggers in the given group
            try:
                tool_group = ToolGroup(self.context.group, self.pbench_run)
            except BadToolGroup as exc:
                click.echo(
                    f'{self.name}: bad tool group specified, "{self.context.group}"'
                    f" ({exc})",
                    err=True,
                )
                return 1
            trigger = tool_group.trigger()
            if trigger:
                print(trigger)

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
        expose_value=False,
        callback=callback,
    )(f)


@click.command(help="list registered triggers")
@common_options
@_group_option
@pass_cli_context
def main(ctxt):
    status = TriggerList(ctxt).execute()
    sys.exit(status)
