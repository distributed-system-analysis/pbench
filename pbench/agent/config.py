import configparser
import os
import pathlib
import sys

from pbench.common import configtools
from pbench.agent.utils import error_out


class AgentConfig:
    def __init__(self, cfg_name=None):
        self.cfg_name = cfg_name
        self.pbench_config = self._get_agent_config()

        self.agent = self.pbench_config["pbench-agent"]
        self.results = self.pbench_config["results"]

    def get_agent(self):
        return self.agent

    def get_results(self):
        return self.results

    def _get_agent_config(self):
        """Agent configuration validation"""
        if self.cfg_name is None:
            self.cfg_name = os.environ.get("_PBENCH_AGENT_CONFIG", None)
            if not self.cfg_name:
                error_out("_PBENCH_AGENT_CONFIG is not set")

        path = pathlib.Path(self.cfg_name)
        if not path.exists():
            error_out(f"{self.cfg_name} does not exist")

        config_files = configtools.file_list(self.cfg_name)
        config_files.reverse()

        try:
            config = configparser.ConfigParser()
            config.read(config_files)
        except configparser.Error as e:
            print(e)
            sys.exit(2)

        return config
