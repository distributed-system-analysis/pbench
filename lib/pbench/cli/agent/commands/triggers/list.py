"""
pbench-list-triggers

This script will list all tool triggers from all tool groups, or list tool
triggers from a specific group.

"""
import sys

import click

from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.commands.triggers.base import TriggerCommand
from pbench.cli.agent.options import common_options


class TriggerList(TriggerCommand):
    """List register triggers"""

    def __init__(self, context):
        super().__init__(context)

    def execute(self):
        if not self.pbench_run.exists():
            # Silently exit if we don't have a pbench run directory.
            return 1

        if not self.context.group:
            # list tool triggers in all groups
            if len(self.groups) == 0:
                self.logger.error("%s: error fetching list of tool groups", self.name)
                return 1

            for group in sorted(self.groups):
                trigger = self.gen_tools_group_dir(group) / "__trigger__"
                if trigger.exists():
                    with open(trigger, "r") as f:
                        data = f.read()
                        print("%s: %s" % (group, data.strip()))
        else:
            # list tool triggers in all groups
            if self.verify_tool_group(self.context.group) != 0:
                self.logger.error(
                    '%s: bad tool group specified, "%s"\n',
                    self.name,
                    self.context.group,
                )
                return 1
            trigger = self.tool_group_dir / "__trigger__"
            if trigger.exists():
                with open(trigger) as f:
                    data = f.read()
                    print(data.strip())

        return 0


def _group_option(f):
    """Group option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.group = value
        return value

    return click.option(
        "-g", "--groups", "--group", expose_value=False, callback=callback,
    )(f)


@click.command(help="list registered triggers")
@common_options
@_group_option
@pass_cli_context
def main(ctxt):
    status = TriggerList(ctxt).execute()
    sys.exit(status)
