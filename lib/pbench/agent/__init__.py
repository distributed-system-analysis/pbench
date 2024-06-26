from configparser import NoOptionError, NoSectionError
from pathlib import Path

from pbench import PbenchConfig
from pbench.common.constants import (
    DEFAULT_PBENCH_AGENT_INSTALL_DIR,
    DEFAULT_PBENCH_AGENT_RUN_DIR,
    DEFAULT_SCP_OPTS,
    DEFAULT_SSH_OPTS,
)
from pbench.common.exceptions import BadConfig


class PbenchAgentConfig(PbenchConfig):
    """PbenchAgentConfig - a sub-class of the PbenchConfig class specifically
    for the pbench agent environment.
    """

    def __init__(self, cfg_name):
        super().__init__(cfg_name)

        try:
            # Provide a few convenience attributes.
            self.agent = self._conf["pbench-agent"]
            self.results = self._conf["results"]
            # Now fetch some default common pbench settings that are required.
            self.pbench_run = Path(
                self.get(
                    "pbench-agent", "pbench_run", fallback=DEFAULT_PBENCH_AGENT_RUN_DIR
                )
            )
            self.pbench_tmp = self.pbench_run / "tmp"
            self.pbench_log = Path(
                self.get(
                    "pbench-agent",
                    "pbench_log",
                    fallback=str(self.pbench_run / "pbench.log"),
                )
            )
            self.pbench_install_dir = Path(
                self.get(
                    "pbench-agent",
                    "install-dir",
                    fallback=DEFAULT_PBENCH_AGENT_INSTALL_DIR,
                )
            )
        except (NoOptionError, NoSectionError, KeyError) as exc:
            raise BadConfig(f"{exc}: {self.files}")
        else:
            if not self.pbench_install_dir.is_dir():
                raise BadConfig(
                    "pbench installation directory,"
                    f" '{self.pbench_install_dir}', does not exist"
                )
            try:
                self.pbench_tmp.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise BadConfig(str(exc))
            self.pbench_bspp_dir = (
                self.pbench_install_dir / "bench-scripts" / "postprocess"
            )
            self.pbench_lib_dir = self.pbench_install_dir / "lib"

        try:
            self.ssh_opts = self.get("results", "ssh_opts", fallback=DEFAULT_SSH_OPTS)
        except (NoOptionError, NoSectionError):
            self.ssh_opts = DEFAULT_SSH_OPTS

        try:
            self.scp_opts = self.get("results", "scp_opts", fallback=DEFAULT_SCP_OPTS)
        except (NoOptionError, NoSectionError):
            self.scp_opts = DEFAULT_SCP_OPTS

        try:
            self._unittests = self.get("pbench-agent", "debug_unittest")
        except Exception:
            self._unittests = False
        else:
            self._unittests = bool(self._unittests)

        try:
            self._debug = self.get("pbench-agent", "debug")
        except Exception:
            self._debug = False
        else:
            self._debug = bool(self._debug)
