import abc
import datetime
import os
import socket
import sys
from pathlib import Path

import click
import six


class BaseCommand(metaclass=abc.ABCMeta):
    """A base class used to define the command interface."""

    def __init__(self, context):
        self.context = context

        if six.PY2:
            click.secho("python3 required, either directly or through SCL", err="red")
            sys.exit(1)
        self.config = self.context.config

        # very first thing to do is figure out which pbench we are
        self.pbench_run = Path(os.environ.get("pbench_run", self.config.pbench_run))
        if not self.pbench_run.exists():
            click.secho(
                f"[ERROR] the provided pbench run directory, {self.pbench_run}, does not exist",
                err="red",
            )
            sys.exit(1)

        # the pbench temporary directory is always relative to the $pbench_run
        # directory
        self.pbench_tmp = Path(os.environ.get("pbench_tmp", (self.pbench_run / "tmp")))
        self.pbench_tmp.mkdir(parents=True, exist_ok=True)
        if not self.pbench_tmp.exists():
            click.secho(
                f"[ERROR] unable to create TMP dir, {self.pbench_tmp}", err="red"
            )
            sys.exit(1)
        self.pbench_log = Path(os.environ.get("pbench_log", self.config.pbench_log))
        self.pbench_install_dir = Path(
            os.environ.get("pbench_install_dir", self.config.pbench_install_dir)
        )
        if not self.pbench_install_dir.exists():
            click.secho(
                f"[ERROR] pbench installation directory, {self.pbench_install_dir}, does not exist",
                err="red",
            )
            sys.exit(1)
        self.pbench_bspp_dir = os.environ.get(
            "pbench_bspp_dir", (self.pbench_install_dir / "bench-scripts/postprocess")
        )
        self.pbench_lib_dir = Path(
            os.environ.get("pbench_lib_dir", self.config.pbench_lib_dir)
        )

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

    def tool_group_dir(self, group):
        return Path(self.pbench_run, f"tools-v1-{group}")

    @property
    def groups(self):
        return [p for p in self.pbench_run.glob("tools-v1-*")]

    def remotes(self, dir):
        return [p for p in dir.iterdir() if p.name != "__trigger__"]

    @abc.abstractclassmethod
    def execute(self):
        """
        This is the main method of the application.
        """
        pass
