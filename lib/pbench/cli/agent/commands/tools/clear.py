"""
pbench-clear-tools

This script will remove tools that have been registered for a particular group.
If no options are used, then all tools from the "default" tool group are removed.
Specifying a tool name and/or remote host will limit the scope of the removal.
"""

import pathlib
import shutil

import click

from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.commands.tools.base import ToolCommand
from pbench.cli.agent.options import common_options


class ClearTools(ToolCommand):
    """Clear registered tools"""

    def __init__(self, context):
        super().__init__(context)

    def execute(self) -> int:
        errors = 0

        if self.verify_tool_group(self.context.group) != 0:
            return 1

        try:
            remotes = self.context.remote.split(",")
        except Exception:
            # We were not given any remotes on the command line, build the list
            # from the tools group directory.
            remotes = self.remote(self.tool_group_dir)
            if not remotes:
                self.logger.error(f'No such group "{self.context.group}".')
                return 1

        tool_not_found = bool(self.context.name)  # Can't not find if not specified
        for remote in remotes:
            tg_dir_r = self.tool_group_dir / remote
            if not tg_dir_r.exists():
                self.logger.warn(
                    'No remote host "%s" in group %s.', remote, self.context.group,
                )
                continue

            if self.context.name:
                names = [self.context.name]
            else:
                # Discover all the tools registered for this remote
                names = self.tools(tg_dir_r)
                if not names:
                    self.logger.warn(
                        'No tools in group "%s" on host "%s".',
                        self.context.group,
                        remote,
                    )

            for name in names:
                status = self._clear_tools(name, remote)
                if status > 0:
                    errors = 1
                elif status == 0:
                    tool_not_found = False

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
                    self.context.group,
                    tg_dir_r.name,
                )
                try:
                    shutil.rmtree(tg_dir_r)
                except OSError:
                    self.logger.error("Failed to remove remote directory %s", tg_dir_r)
                    errors = 1

        if tool_not_found:
            self.logger.warn(f'Tool "{self.context.name}" not found')

        return 0 if errors == 0 else 1

    def _clear_tools(self, name, remote) -> int:
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
                'Removed "%s" from host "%s" in tools group "%s"',
                name,
                remote,
                self.context.group,
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
