"""
pbench-list-tools

This script can list all tools from all groups, list tools from a specific
group, or list which groups contain a specific tool

"""

import sys

import click

from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.commands.tools.base import ToolCommand
from pbench.cli.agent.options import common_options
from pbench.agent.tool_group import BadToolGroup

# FIX:
# the set of error codes is currently
# 0
# 1 = Bad tool group
# 2 = anything else


class ListTools(ToolCommand):
    """ List registered Tools """

    def __init__(self, context):
        super(ListTools, self).__init__(context)

    def execute(self):
        if not self.pbench_run.exists():
            self.logger.warn("The %s directory does not exist", self.pbench_run)
            # FIX: do we want to distinguish this from the "bad name" code below.
            return 2

        status = 0
        # list tools in one or all groups
        if self.context.group:
            groups = self.context.group
        else:
            groups = self.groups

        if not self.context.name:
            host_tools = {}
            for group in groups:
                host_tools[group] = {}
                try:
                    for path in self.gen_tools_group_dir(group).glob("*/**"):
                        if self.context.with_option:
                            host_tools[group][path.name] = [
                                p.read_text() for p in self.tools(path)
                            ]
                        else:
                            host_tools[group][path.name] = [p.name for p in self.tools(path)]
                except BadToolGroup:
                    self.logger.error("Bad tool group name: %s", group)
                    return 1
            if host_tools:
                for k, v in host_tools.items():
                    for h, t in v.items():
                        print(f"{k}: {h} {t}")
        else:
            # List the groups which include this tool
            group_list = []
            for group in groups:
                try:
                    tg_dir = self.gen_tools_group_dir(group)
                    if not tg_dir.exists():
                        self.logger.error("bad or missing tool group %s", group)
                        status = 1
                        continue
                except BadToolGroup:
                    self.logger.error("Bad Tool Group: %s", group)
                    status = 1
                    continue
                for path in tg_dir.iterdir():
                    # Check to see if the tool is in any of the hosts.
                    if self.context.name in [tool.name for tool in self.tools(path)]:
                        group_list.append(group)
            if group_list:
                print(f"tool name: {self.context.name} groups: {', '.join(group_list)}")
            elif status == 0:
                # the group list is empty but not because of a bad tool group, so set an "other"
                status = 2
        return status


def _group_option(f):
    """Group name option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        try:
            clictxt.group = value.split()
        except Exception:
            clictxt.group = []
        return value

    return click.option(
        "-g",
        "--group",
        expose_value=False,
        callback=callback,
        help="list the tools used in this <group-name>",
    )(f)


def _name_option(f):
    """Name of the tool option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.name = value
        return value

    return click.option(
        "-n",
        "--name",
        expose_value=False,
        callback=callback,
        help=(
            "list the tool groups in which <tool-name> is used.\n"
            "Not allowed with the --group option"
        ),
    )(f)


def _with_option(f):
    """display options with tools"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.with_option = value
        return value

    return click.option(
        "-o",
        "--with-option",
        is_flag=True,
        expose_value=False,
        callback=callback,
        help=("list the options with each tool"),
    )(f)


@click.command()
@common_options
@_name_option
@_group_option
@_with_option
@pass_cli_context
def main(ctxt):
    status = ListTools(ctxt).execute()
    sys.exit(status)
