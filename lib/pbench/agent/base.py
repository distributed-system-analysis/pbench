import abc
import datetime
import os
import pathlib
import socket
import sys

import click

from pbench.agent import PbenchAgentConfig


class BaseCommand(metaclass=abc.ABCMeta):
    """A base class used to define the command interface."""

    def __init__(self, context):
        self.context = context

        self.config = PbenchAgentConfig(self.context.config)
        self.name = os.path.basename(sys.argv[0])

        self.pbench_run = self.config.pbench_run
        if not self.pbench_run.exists():
            click.secho(
                f"[ERROR] the provided pbench run directory, {self.pbench_run}, does not exist"
            )
            sys.exit(1)

        # the pbench temporary directory is always relative to the $pbench_run
        # directory
        self.pbench_tmp = self.pbench_run / "tmp"
        if not self.pbench_tmp.exists():
            try:
                os.makedirs(self.pbench_tmp)
            except OSError:
                click.secho(f"[ERROR] unable to create TMP dir, {self.pbench_tmp}")
                sys.exit(1)

        # log file - N.B. not a directory
        self.pbench_log = self.config.pbench_log
        if self.pbench_log is None:
            self.pbench_log = self.pbench_run / "pbench.log"

        self.pbench_install_dir = self.config.pbench_install_dir
        if self.pbench_install_dir is None:
            self.pbench_install_dir = "/opt/pbench-agent"
        if not self.pbench_install_dir.exists():
            click.secho(
                f"[ERROR] pbench installation directory, {self.pbench_install_dir}, does not exist"
            )
            sys.exit(1)

        self.pbench_bspp_dir = self.pbench_install_dir / "bench-scripts" / "postprocess"
        self.pbench_lib_dir = self.pbench_install_dir / "lib"

        self.ssh_opts = self.config.ssh_opts
        os.environ["ssh_opts"] = self.ssh_opts

        self.scp_opts = self.config.scp_opts
        os.environ["scp_opts"] = self.scp_opts

        os.environ["_pbench_debug_mode"] = "0"
        if os.environ.get("_PBENCH_UNIT_TESTS"):
            self.date = "1900-01-01T00:00:00"
            self.date_suffix = "1900.01.01T00.00.00"
            self.hostname = "testhost"
            self.full_hostname = "testhost.example.com"
        else:
            self.date = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%s")
            self.date_suffix = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H.%M.%s")
            self.hostname = socket.gethostname()
            self.full_hostname = socket.getfqdn()

        # Backwards compatibility and for toolmeister
        pbench_env = {
            "date": self.date,
            "date_suffix": self.date_suffix,
            "hostname": self.hostname,
            "full_hostname": self.full_hostname,
            "pbench_run": str(self.pbench_run),
            "pbench_install_dir": str(self.pbench_install_dir),
            "pbench_tmp": str(self.pbench_tmp),
            "pbench_log": str(self.pbench_log),
            "pbench_bspp_dir": str(self.pbench_bspp_dir),
            "pbench_lib_dir": str(self.pbench_lib_dir),
        }
        for k, v in pbench_env.items():
            os.environ[k] = v

    @abc.abstractmethod
    def execute(self):
        """
        This is the main method of the application
        """
        pass

    def get_path(self, path):
        """Converts a string path into a pathlib object"""
        if path is None:
            return path
        elif not isinstance(path, pathlib.PurePath):
            return pathlib.Path(path)
        else:
            return path

    def verify_tool_group(self, group):
        """Ensure we have a tools group directory to work with"""
        self.tool_group_dir = self.pbench_run / f"tools-v1-{group}"
        if not self.tool_group_dir.exists():
            click.secho(
                f'\t{self.name}: invalid --group option ("{group}"), directory not found: {self.tool_group_dir}'
            )
            ctxt = click.get_current_context()
            click.echo(ctxt.get_help())
            return 1
        return 0
