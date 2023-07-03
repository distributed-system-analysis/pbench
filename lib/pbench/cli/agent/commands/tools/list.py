"""
pbench-list-tools

This script lists all tools from all groups, all tools from a specific group,
or all groups which contain a specific tool.

"""

import click

from pbench.agent.tool_group import BadToolGroup
from pbench.cli import CliContext, pass_cli_context
from pbench.cli.agent.commands.tools.base import ToolCommand
from pbench.cli.agent.options import common_options


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
            for host, hostitems in sorted(gval.items()):
                label = hostitems["label"]
                host_string = f"host: {host}" + (f", label: {label}" if label else "")
                tools = hostitems["tools"]
                if tools:
                    if not with_option:
                        tool_string = ", ".join(sorted(tools.keys()))
                    else:
                        tools_with_options = (
                            f"{t} {' '.join(v)}" for t, v in sorted(tools.items())
                        )
                        tool_string = ", ".join(tools_with_options)
                    print(f"group: {group}; {host_string}; tools: {tool_string}")
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
        toolname = self.context.name
        found = False
        tool_info = {}

        for group in groups:
            tool_info[group] = {}
            try:
                tg_dir = self.gen_tools_group_dir(group)
            except BadToolGroup:
                self.logger.error("Bad tool group: %s", group)
                return 1

            for path in tg_dir.iterdir():
                # skip __trigger__ if present
                if not path.is_dir():
                    continue

                host = path.name
                tool_info[group][host] = {"label": None, "tools": {}}

                toolsdict = tool_info[group][host]["tools"]
                if toolname:
                    # Check if the tool is in any of the hosts.
                    found = toolname in self.tools(path)
                    toolslist = [toolname] if found else []
                else:
                    # no tool name was specified
                    toolslist = sorted(self.tools(path))

                    label = path / "__label__"
                    v = label.read_text().rstrip("\n") if label.exists() else None
                    tool_info[group][host]["label"] = v

                for tool in toolslist:
                    v = (path / tool).read_text().rstrip("\n").split("\n")
                    toolsdict[tool] = sorted(v) if opts else ""

        if toolname:
            if found:
                self.print_results(tool_info, self.context.with_option)
                return 0
            else:
                msg = f'Tool "{toolname}" not found in '
                msg += self.context.group[0] if self.context.group else "any group"
                self.logger.error(msg)
                return 1

        elif tool_info:
            found = self.print_results(tool_info, self.context.with_option)
            if not found:
                msg = "No tools found"
                if self.context.group:
                    msg += f' in group "{self.context.group[0]}"'
                self.logger.warn(msg)
        else:
            self.logger.warn("No tool groups found")

        return 0


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
