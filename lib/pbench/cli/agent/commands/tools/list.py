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


class ListTools(ToolCommand):
    """ List registered Tools """

    def __init__(self, context):
        super(ListTools, self).__init__(context)

    @staticmethod
    def print_results(toolinfo: dict, tool: str, with_option: bool):
        for group in sorted(toolinfo.keys()):
            for host in sorted(toolinfo[group].keys()):
                tools = toolinfo[group][host]
                if tools:
                    if not with_option:
                        s = ", ".join(sorted(tools.keys()))
                    else:
                        tools_with_options = [f"{t} {' '.join(tools[t])}" for t in sorted(tools.keys())]
                        s = ", ".join( tools_with_options)
                    print(f"group: {group}; host: {host}; tools: {s}")

    def execute(self):
        if not self.pbench_run.exists():
            self.logger.warn("The %s directory does not exist", self.pbench_run)
            return 0

        # list tools in one or all groups
        if self.context.group:
            groups = self.context.group
        else:
            groups = self.groups

        opts = self.context.with_option
        tool_info = {}

        if not self.context.name:
            for group in groups:
                tool_info[group] = {}
                try:
                    for path in self.gen_tools_group_dir(group).glob("*/**"):
                        host = path.name
                        tool_info[group][host] = {}
                        for tool in sorted(self.tools(path)):
                            tool_info[group][host][tool] = sorted((path / tool).read_text().rstrip('\n').split('\n')) if opts else ""
                except BadToolGroup:
                    self.logger.error("Bad tool group: %s", group)
                    return 1
            if tool_info:
                self.print_results(tool_info, None, self.context.with_option)
        else:
            # List the groups which include this tool
            tool = self.context.name
            found = False
            for group in groups:
                try:
                    tg_dir = self.gen_tools_group_dir(group)
                except BadToolGroup:
                    self.logger.error("Bad tool group: %s", group)
                    return 1

                tool_info[group] = {}
                for path in tg_dir.iterdir():
                    # skip files like __label__ and __trigger__
                    if not path.is_dir():
                        continue

                    host = path.name
                    tool_info[group][host] = {}
                    # Check to see if the tool is in any of the hosts.
                    if tool in self.tools(path):
                        tool_info[group][host][tool] = sorted((path / tool).read_text().rstrip("\n").split('\n')) if opts else ""
                        found = True
            if found:
                self.print_results(tool_info, tool, self.context.with_option)
            else:
                self.logger.error(
                    "Tool does not exist in any group: %s", self.context.name
                )
                return 1


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
