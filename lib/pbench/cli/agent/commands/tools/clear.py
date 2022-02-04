"""
pbench-clear-tools

This script will remove tools that have been registered for a particular group.
If no options are used, then all tools from the "default" tool group are removed.
Specifying a tool name and/or remote host will limit the scope of the removal.
"""

import pathlib
import shutil

import click
from typing import Union

from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.commands.tools.base import ToolCommand
from pbench.cli.agent.options import common_options


class ClearTools(ToolCommand):
    """Clear registered tools"""

    def __init__(self, context):
        super().__init__(context)

    def execute(self) -> int:
        errors = 0

        groups = self.context.group.split(",")
        # groups is never empty and if the user doesn't specify a --group,
        # then it has the value "default"
        for group in groups:
            if self.verify_tool_group(group) != 0:
                self.logger.warn(f'No such group "{group}".')
                errors = 1
                continue

            errors, tools_not_found = self._clear_remotes(group)

            if self.context.name and tools_not_found:
                self.logger.warn(
                    f"Tools {sorted(tools_not_found)} not found in group {group}"
                )

            # Remove a custom (non-default) tool group directory if there are
            # no tools registered anymore under this group
            if group != "default" and not any(self.tool_group_dir.iterdir()):
                try:
                    shutil.rmtree(self.tool_group_dir)
                except OSError:
                    self.logger.error(
                        "Failed to remove group directory %s", self.tool_group_dir
                    )
                    errors = 1

        return errors

    def _clear_remotes(self, group) -> Union[int, list]:
        errors = 0
        tools_not_found = []
        if self.context.remote:
            remotes = self.context.remote.split(",")
        else:
            # We were not given any remotes on the command line, build the list
            # from the tools group directory.
            remotes = self.remote(self.tool_group_dir)
            if (
                not remotes
                and group != "default"
                and self.is_empty(self.tool_group_dir)
            ):
                # Unless it is not a default group we will remove any
                # empty tool directories lingering or wasn't cleaned before.
                try:
                    shutil.rmtree(self.tool_group_dir)
                except OSError as e:
                    self.logger.error(
                        "Failed to remove empty group directory %s\n%s",
                        self.tool_group_dir,
                        str(e),
                    )

        for remote in remotes:
            tg_dir_r = self.tool_group_dir / remote
            if not tg_dir_r.exists():
                self.logger.warn(
                    'No remote host "%s" in group %s.', remote, group,
                )
                continue

            if self.context.name:
                names = self.context.name.split(",")
            else:
                # Discover all the tools registered for this remote
                names = self.tools(tg_dir_r)
                if not names:
                    # FIXME:  this is another odd case -- the remote subdirectory
                    #  exists, but it's empty.  (We'll remove it below.)
                    self.logger.warn(
                        'No tools in group "%s" on host "%s".', group, remote,
                    )

            for name in names:
                status = self._clear_tools(name, remote, group)
                if status:
                    tools_not_found.append(name)
                    if status > 0:
                        errors = 1

            tool_files = [p.name for p in tg_dir_r.iterdir()]

            if len(tool_files) == 1 and tool_files[0] == "__label__":
                label = tg_dir_r / "__label__"
                try:
                    label.unlink()
                except Exception:
                    self.logger.error("Failed to remove label for remote %s", tg_dir_r)
                    errors = 1

            if self.is_empty(tg_dir_r):
                self.logger.info(
                    'All tools removed from group "%s" on host "%s"',
                    group,
                    tg_dir_r.name,
                )
                try:
                    shutil.rmtree(tg_dir_r)
                except OSError:
                    self.logger.error("Failed to remove remote directory %s", tg_dir_r)
                    errors = 1
        return errors, tools_not_found

    def _clear_tools(self, name, remote, group) -> int:
        """
        Remove specified tool and associated files

        Returns zero for success, -1 for name-not-found, and 1 for failure.
        """
        tpath = self.tool_group_dir / remote / name
        try:
            tpath.unlink()
        except FileNotFoundError:
            self.logger.debug('Tool "%s" not registered for remote "%s"', name, remote)
            return -1
        except Exception as exc:
            self.logger.error("Failed to remove %s: %s", tpath, exc)
            ret_val = 1
        else:
            noinstall = pathlib.Path(f"{tpath}.__noinstall__")
            try:
                noinstall.unlink()
            except FileNotFoundError:
                ret_val = 0
            except Exception as exc:
                self.logger.error("Failure to remove %s: %s", noinstall, exc)
                ret_val = 1
            else:
                ret_val = 0

        if ret_val == 0:
            self.logger.info(
                'Removed "%s" from host "%s" in tools group "%s"', name, remote, group,
            )
        return ret_val

    @staticmethod
    def is_empty(path):
        """Determine if directory is empty"""
        return not any(path.iterdir())


def _group_option(f):
    """Group name option"""

    def callback(ctxt, _param, value):
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
