import abc
import datetime
import os
import pathlib
import socket
import sys

import click

from pbench.agent import PbenchAgentConfig
from pbench.agent.tool_group import ToolGroup, BadToolGroup
from pbench.agent.utils import setup_logging


class BaseCommand(metaclass=abc.ABCMeta):
    """A base class used to define the command interface."""

    def __init__(self, context):
        self.context = context

        self.config = PbenchAgentConfig(self.context.config)
        self.name = os.path.basename(sys.argv[0])

        env_pbench_run = os.environ.get("pbench_run")
        if env_pbench_run:
            pbench_run = pathlib.Path(env_pbench_run)
            if not pbench_run.is_dir():
                click.echo(
                    f"[ERROR] the provided pbench run directory, {env_pbench_run}, does not exist",
                    err=True,
                )
                click.get_current_context().exit(1)
            self.pbench_run = pbench_run
        else:
            self.pbench_run = pathlib.Path(self.config.pbench_run)
            if not self.pbench_run:
                self.pbench_run = pathlib.Path("/var/lib/pbench-agent")
            try:
                self.pbench_run.mkdir(exist_ok=True)
            except Exception as exc:
                click.secho(
                    f"[ERROR] unable to create pbench_run directory, '{self.pbench_run}': '{exc}'"
                )
                click.get_current_context().exit(1)

        # the pbench temporary directory is always relative to the $pbench_run
        # directory
        self.pbench_tmp = self.pbench_run / "tmp"
        try:
            self.pbench_tmp.mkdir(exist_ok=True)
        except Exception as exc:
            click.secho(
                f"[ERROR] unable to create TMP directory, '{self.pbench_tmp}': '{exc}'"
            )
            click.get_current_context().exit(1)

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
            click.get_current_context().exit(1)

        self.pbench_bspp_dir = self.pbench_install_dir / "bench-scripts" / "postprocess"
        self.pbench_lib_dir = self.pbench_install_dir / "lib"

        self.logger = setup_logging(debug=False, logfile=self.pbench_log)

        self.ssh_opts = os.environ.get("ssh_opts", self.config.ssh_opts)
        self.scp_opts = os.environ.get("scp_opts", self.config.scp_opts)

        ut = os.environ.get("_PBENCH_UNIT_TESTS")
        self.hostname = "testhost" if ut else socket.gethostname()
        self.full_hostname = "testhost.example.com" if ut else socket.getfqdn()
        now = datetime.datetime.utcnow()
        if ut:
            now = datetime.datetime(1900, 1, 1, tzinfo=datetime.timezone.utc)
        self.date = now.strftime("%FT%H:%M:%S")
        self.date_suffix = now.strftime("%Y.%m.%dT%H.%M.%S")

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
        try:
            self.tool_group_dir = self.gen_tools_group_dir(group)
        except BadToolGroup as exc:
            click.echo(
                f'{self.name}: invalid --group option "{group}" ({exc})', err=True
            )
            ret_code = 1
        else:
            ret_code = 0
        return ret_code

    def gen_tools_group_dir(self, group):
        return ToolGroup.verify_tool_group(group, pbench_run=self.pbench_run)
