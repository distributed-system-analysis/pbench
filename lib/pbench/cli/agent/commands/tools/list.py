"""
pbench-list-tools

This script can list all tools from all groups, list tools from a specific
group, or list which groups contain a specific tool

"""

import sys

import click

from pbench.agent.tool_group import BadToolGroup
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.commands.tools.base import ToolCommand
from pbench.cli.agent.options import common_options


class ListTools(ToolCommand):
    """ List registered Tools """

    def __init__(self, context):
        super(ListTools, self).__init__(context)

    @staticmethod
    def print_results(toolinfo, with_options):
        for group, rest in toolinfo.items():
            for host, tools in rest.items():
                if not with_options:
                    s = ",".join(tools)
                else:
                    s = ",".join(map(lambda x: " ".join(x), tools))
                print("%s: %s: %s" % (group, host, s))

    def execute(self):
        if not self.pbench_run.exists():
            self.logger.warn("The %s directory does not exist", self.pbench_run)
            return 0

        # list tools in one or all groups
        if self.context.group:
            groups = self.context.group
        else:
            groups = self.groups

        with_option = False
        if not self.context.name:
            host_tools = {}
            for group in groups:
                host_tools[group] = {}
                try:
                    for path in self.gen_tools_group_dir(group).glob("*/**"):
                        host = path.name
                        if self.context.with_option:
                            with_option = True
                            host_tools[group][host] = [
                                (p, (path / p).read_text().rstrip("\n")) for p in self.tools(path)
                            ]
                        else:
                            host_tools[group][host] = [p for p in self.tools(path)]
                except BadToolGroup:
                    self.logger.error("Tool group does not exist: %s", group)
                    return 1
            if host_tools:
                self.print_results(host_tools, with_option)
        else:
            # List the groups which include this tool
            group_list = []
            tool = self.context.name
            options = {}
            for group in groups:
                try:
                    tg_dir = self.gen_tools_group_dir(group)
                except BadToolGroup:
                    self.logger.error("Tool group does not exist: %s", group)
                    return 1

                for path in tg_dir.iterdir():
                    # skip files like __label__ and __trigger__
                    if not path.is_dir():
                        continue

                    host = path.name
                    # Check to see if the tool is in any of the hosts.
                    if tool in self.tools(path):
                        group_list.append(group)
                        if self.context.with_option:
                            with_option = True
                            options[group] = (host, (path / tool).read_text().rstrip("\n"))

            if group_list:
                if with_option:
                    print("tool name: %s" % (tool))
                    for group, rest in options.items():
                        host, options = rest
                        print("group: %s, host: %s, options: %s" % (group, host, options))
                else:
                    print(
                        "tool name: %s groups: %s"
                        % (tool, ", ".join(group_list))
                    )
            else:
                # name does not exist in any group
                self.logger.error("Tool does not exist in any group: %s", tool)
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
