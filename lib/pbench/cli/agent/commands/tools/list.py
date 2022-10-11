"""
pbench-list-tools

This script lists all tools from all groups, all tools from a specific group,
or all groups which contain a specific tool.

"""
from typing import Iterable

import click

from pbench.agent.tool_group import BadToolGroup, ToolGroup
from pbench.cli.agent import BaseCommand, CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class ListTools(BaseCommand):
    """List registered Tools"""

    def __init__(self, context):
        super(ListTools, self).__init__(context)

    @staticmethod
    def print_results(toolinfo: dict, with_option: bool) -> bool:
        """Print the gathered results."""
        for group, gval in sorted(toolinfo.items()):
            for host, tools in sorted(gval.items()):
                if not with_option:
                    s = ", ".join(sorted(tools.keys()))
                else:
                    tools_with_options = [f"{t} {v}" for t, v in sorted(tools.items())]
                    s = ", ".join(tools_with_options)
                print(f"group: {group}; host: {host}; tools: {s}")

    def gen_tool_groups(self) -> Iterable[ToolGroup]:
        """Provide an interable for all the ToolGroup objects being considered.

        If one or more groups are provided on the command line, individual
        ToolGroup objects are created and returned in a list so that invalid
        tool groups can be flagged early.

        If no groups are provided on the command line, we ask the ToolGroup
        class to provide the list.

        Will cause the command to exit with an error if a bad tool group is
        encountered.
        """
        if self.context.group:
            tool_groups = []
            for group in self.context.group:
                try:
                    tool_groups.append(ToolGroup(group, self.pbench_run))
                except BadToolGroup:
                    self.logger.error("Bad tool group: %s", group)
                    click.get_current_context().exit(1)
        else:
            tool_groups = list(ToolGroup.gen_tool_groups(self.pbench_run))
        return tool_groups

    def execute(self) -> int:
        # Generate the list of ToolGroups to target.
        tool_groups = self.gen_tool_groups()
        opts = self.context.with_option
        tool_name = self.context.name
        tool_info = {}

        if not tool_name:
            if not tool_groups:
                self.logger.warn("No tool groups found")
                return 0

            # List all tools in the target groups
            for tool_group in tool_groups:
                hostnames = tool_group.hostnames()
                if hostnames:
                    tool_info[tool_group.name] = hostnames
        else:
            # List the groups which include this tool
            for tool_group in tool_groups:
                hosts = tool_group.toolnames().get(tool_name, {})
                if not hosts:
                    # This group has no hosts with the given tool name
                    # registered.
                    continue
                for host, opts in hosts.items():
                    if tool_group.name not in tool_info:
                        tool_info[tool_group.name] = {}
                    tool_info[tool_group.name][host] = dict([(tool_name, opts)])

        if tool_info:
            self.print_results(tool_info, opts)
            ret_val = 0
        else:
            if tool_name:
                msg = f'Tool "{self.context.name}" not found in '
                msg += self.context.group[0] if self.context.group else "any group"
                ret_val = 1
            else:
                msg = "No tools found"
                if self.context.group:
                    msg += f' in group "{self.context.group[0]}"'
                ret_val = 0
            self.logger.warn(msg)

        return ret_val


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
