"""pbench-clear-tools

This script will remove tools that have been registered for a particular group.
If no options are used, then all tools from the "default" tool group are removed.
Specifying a tool name and/or remote host will limit the scope of the removal.
"""

import click

from pbench.agent.tool_group import BadToolGroup, HostNotFound, ToolGroup, ToolNotFound
from pbench.cli.agent import BaseCommand, CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class ClearTools(BaseCommand):
    """Clear registered tools"""

    def __init__(self, context):
        super().__init__(context)

    def execute(self) -> int:
        ret_val = 0

        tool_groups = []
        # The list of tool groups is never empty, and if the user doesn't
        # specify a --group, then it has the value "default".
        for group in self.context.group.split(","):
            try:
                tool_group = ToolGroup(group, self.pbench_run)
            except BadToolGroup as exc:
                self.logger.warn('No such group "%s", %s.', group, exc)
                ret_val = 1
            else:
                if not tool_group.is_empty():
                    # Do not try to clear tools from empty tool groups.
                    tool_groups.append(tool_group)
        if not tool_groups:
            return ret_val

        # We have at least one tool group to consider.

        if self.context.remote:
            # Remove specific hosts from the group.
            host_names = self.context.remote.split(",")
        else:
            # Remove all hosts found in the group.
            host_names = None

        if self.context.name:
            # Remove specific tool names from the group.
            tool_names = self.context.name.split(",")
        else:
            # Remove all tools in the group.
            tool_names = None

        for tg in tool_groups:
            tools_not_found = {}
            hosts_not_found = []
            if not tool_names:
                # No specific tools listed to unregister, so we'll unregister
                # the whole host.
                if not host_names:
                    # No specific list of hosts, so unregister all hosts.
                    lcl_host_names = tg.hostnames().keys()
                else:
                    lcl_host_names = host_names
                for host_name in lcl_host_names:
                    try:
                        tg.unregister_host(host_name)
                    except HostNotFound:
                        hosts_not_found.append(host_name)
                    except Exception as exc:
                        self.logger.error(
                            "Error unregistering all tools for host %s, '%s'",
                            host_name,
                            exc,
                        )
                        return 1
            else:
                # We have a specific list of tools to unregister.
                if not host_names:
                    # No specific list of hosts, so unregister tools from all
                    # hosts.
                    lcl_host_names = tg.hostnames().keys()
                else:
                    lcl_host_names = host_names
                for host_name in lcl_host_names:
                    for tool_name in tool_names:
                        try:
                            tg.unregister_tool(host_name, tool_name)
                        except ToolNotFound:
                            if host_name not in tools_not_found:
                                tools_not_found[host_name] = []
                            tools_not_found[host_name].append(tool_name)
                        except Exception as exc:
                            self.logger.error(
                                "Error unregistering tool %s for host %s, '%s'",
                                tool_name,
                                host_name,
                                exc,
                            )
                            return 1

            if hosts_not_found:
                self.logger.warn(
                    f"Hosts {sorted(hosts_not_found)} not found in group {tg.name}"
                )
            if tools_not_found:
                for host_name, tools in tools_not_found.items():
                    self.logger.warn(
                        f"Tools {sorted(tools)} not found in remote {host_name}"
                        f" and group {tg.name}"
                    )

        for tg in tool_groups:
            if tg.is_empty():
                self.logger.info('All tools removed from group "%s" on host')
        return 0


def contains_empty(items: str) -> bool:
    """Determine if the comma separated string contains en empty element"""
    return not all(items.split(","))


def _group_option(f):
    """Group name option"""

    def callback(ctxt, _param, value):
        if value and contains_empty(value):
            raise click.BadParameter(message="Blank group name specified.")
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.group = value
        return value

    return click.option(
        "-g",
        "--group",
        "--groups",
        default="default",
        expose_value=False,
        callback=callback,
        help=(
            "Clear the tools in the <group-name> group.  "
            "If no group is specified, the 'default' group is assumed."
        ),
    )(f)


def _name_option(f):
    """Tool name to use"""

    def callback(ctxt, _param, value):
        if value and contains_empty(value):
            raise click.BadParameter(message="Blank tool name specified.")
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.name = None
        if value:
            clictxt.name = value
        return value

    return click.option(
        "-n",
        "--name",
        "--names",
        expose_value=False,
        callback=callback,
        help="Clear only the <tool-name> tool.",
    )(f)


def _remote_option(f):
    """Remote hostname"""

    def callback(ctxt, _param, value):
        if value and contains_empty(value):
            raise click.BadParameter(message="Blank remote name specified.")
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.remote = value
        return value

    return click.option(
        "-r",
        "--remote",
        "--remotes",
        expose_value=False,
        callback=callback,
        help=(
            "Clear the tool(s) only on the specified remote(s).  "
            "Multiple remotes may be specified as a comma-separated list.  "
            "If no remote is specified, all remotes are cleared."
        ),
    )(f)


@click.command(help="clear all tools or filter by name or group")
@common_options
@_name_option
@_group_option
@_remote_option
@pass_cli_context
def main(ctxt):
    status = ClearTools(ctxt).execute()
    click.get_current_context().exit(status)
