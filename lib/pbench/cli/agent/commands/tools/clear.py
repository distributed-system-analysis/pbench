"""
pbench-clear-tools

This script will remove tools that have been registered.  If no options are
used, then all tools from the "default" tool group are removed.  Specifying
a tool name and/or remote host will limit the scope of the removal.


"""
import logging
import shutil
import sys
import pathlib

import click

from pbench.agent.utils import setup_logging
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.commands.tools.base import ToolCommand
from pbench.cli.agent.options import common_options

LOG = logging.getLogger(__name__)


class ClearTools(ToolCommand):
    """Clear registered tools"""

    def __init__(self, context):
        super().__init__(context)

        setup_logging(debug=False, logfile=self.pbench_log)

    def execute(self):
        errors = 0

        if self.verify_tool_group(self.context.group) != 0:
            return 1

        try:
            remotes = self.context.remote.split(",")
        except Exception:
            # We were not given any remotes on the command line, build the list
            # from the tools group directory.
            remotes = self.remote(self.tool_group_dir)

        for remote in remotes:
            tg_dir_r = self.tool_group_dir / remote
            if not tg_dir_r.exists():
                LOG.warn(
                    'The given remote host, "%s", is not a directory in' " %s.",
                    remote,
                    self.tool_group_dir,
                )
                continue

            if self.context.name:
                names = self.context.name
            else:
                # Discover all the tools registered for this remote
                names = self.tools(tg_dir_r)

            for name in names:
                status = self._clear_tools(name, remote)
                if status != 0:
                    errors += 1

            tool_files = [p.name for p in tg_dir_r.iterdir()]

            if len(tool_files) == 1 and tool_files[0] == "__label__":
                label = tg_dir_r / "__label__"
                try:
                    label.unlink()
                except Exception:
                    LOG.error("Failed to remove label for remote %s", tg_dir_r)
                    errors += 1

            if self.is_empty(tg_dir_r):
                LOG.info('All tools removed from host, "%s"', tg_dir_r.name)
                try:
                    shutil.rmtree(tg_dir_r)
                except OSError:
                    LOG.error("Failed to remove remote directory %s", tg_dir_r)
                    errors += 1

        return errors

    def _clear_tools(self, name, remote):
        """Remove specified tool and associated files"""
        tpath = self.tool_group_dir / remote / name
        try:
            tpath.unlink()
        except FileNotFoundError:
            LOG.debug('Tool "%s" not registered for remote "%s"', name, remote)
            return 0
        except Exception as exc:
            LOG.error("Failed to remove %s: %s", tpath, exc)
            ret_val = 1
        else:
            noinstall = pathlib.Path(f"{tpath}.__noinstall__")
            try:
                noinstall.unlink()
            except FileNotFoundError:
                ret_val = 0
            except Exception as exc:
                LOG.error("Failure to remove %s: %s", noinstall, exc)
                ret_val = 1
            else:
                ret_val = 0

        if ret_val == 0:
            LOG.info(
                'Removed "%s" from host, "%s", in tools group, "%s"',
                name,
                remote,
                self.context.group,
            )
        return ret_val

    def is_empty(self, path):
        """Determine if directory is empty or not"""
        for dirent in path.iterdir():
            return False
        return True


def _group_option(f):
    """Group name option"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.group = value
        return value

    return click.option(
        "-g",
        "--group",
        default="default",
        required=True,
        expose_value=False,
        callback=callback,
        help="list the tools used in this <group-name>",
    )(f)


def _name_option(f):
    """Tool name to use"""

    def callback(ctxt, param, value):
        clictxt = ctxt.ensure_object(CliContext)
        clictxt.name = []
        if value:
            clictxt.name.append(value)
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


def _remote_option(f):
    """Remote hostname"""

    def callback(ctxt, param, value):
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
            "a specific remote on which tools needs to be cleared.\n"
            "If no remote is specified, all the tools on all remotes are removed"
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
    sys.exit(status)
