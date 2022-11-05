"""
pbench-list-tools

This script lists all tools from all groups, all tools from a specific group,
or all groups which contain a specific tool.

"""

import click

from pbench.agent.cli import CliContext, pass_cli_context
from pbench.agent.cli.commands.tools.base import ToolCommand
from pbench.agent.cli.options import common_options
from pbench.agent.tool_group import BadToolGroup


class ListTools(ToolCommand):
    """List registered Tools"""

    def __init__(self, context):
        super(ListTools, self).__init__(context)

    @staticmethod
    def print_results(toolinfo: dict, with_option: bool) -> bool:
        """
        Print the results.

        Return True indicating that something was printed.
        """
        printed = False
        for group, gval in sorted(toolinfo.items()):
            for host, tools in sorted(gval.items()):
                if tools:
                    if not with_option:
                        s = ", ".join(sorted(tools.keys()))
                    else:
                        tools_with_options = [
                            f"{t} {' '.join(v)}" for t, v in sorted(tools.items())
                        ]
                        s = ", ".join(tools_with_options)
                    print(f"group: {group}; host: {host}; tools: {s}")
                    printed = True
        return printed

    def execute(self) -> int:
        if not self.pbench_run.exists():
            self.logger.warn("The %s directory does not exist", self.pbench_run)
            return 1

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
                    tg_dir = self.gen_tools_group_dir(group).glob("*/**")
                except BadToolGroup:
                    self.logger.error("Bad tool group: %s", group)
                    return 1

                for path in tg_dir:
                    host = path.name
                    tool_info[group][host] = {}
                    for tool in sorted(self.tools(path)):
                        tool_info[group][host][tool] = (
                            sorted((path / tool).read_text().rstrip("\n").split("\n"))
                            if opts
                            else ""
                        )

            if tool_info:
                found = self.print_results(tool_info, self.context.with_option)
                if not found:
                    msg = "No tools found"
                    if self.context.group:
                        msg += f' in group "{self.context.group[0]}"'
                    self.logger.warn(msg)
            else:
                self.logger.warn("No tool groups found")

            return 0

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
                        tool_info[group][host][tool] = (
                            sorted((path / tool).read_text().rstrip("\n").split("\n"))
                            if opts
                            else ""
                        )
                        found = True

            if found:
                self.print_results(tool_info, self.context.with_option)
                return 0
            else:
                msg = f'Tool "{self.context.name}" not found in '
                msg += self.context.group[0] if self.context.group else "any group"
                self.logger.error(msg)
                return 1


def _group_option(f):
    """Group name option"""

    def callback(ctxt, _param, value):
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

    def callback(ctxt, _param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.name = value
        return value

    return click.option(
        "-n",
        "--name",
        expose_value=False,
        callback=callback,
        help=("list the tool groups in which <tool-name> is used."),
    )(f)


def _with_option(f):
    """display options with tools"""

    def callback(ctxt, _param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.with_option = value
        return value

    return click.option(
        "-o",
        "--with-option",
        is_flag=True,
        expose_value=False,
        callback=callback,
        help="list the options with each tool",
    )(f)


@click.command(help="list all tools or filter by name or group")
@common_options
@_name_option
@_group_option
@_with_option
@pass_cli_context
def main(ctxt):
    status = ListTools(ctxt).execute()
    click.get_current_context().exit(status)
