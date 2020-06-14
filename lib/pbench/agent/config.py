import configparser
import pathlib
import sys

import click

from pbench.common import configtools
from pbench.common import exceptions


def lookup_agent_configuration(filename):
    """Return config file PATH"""
    path = pathlib.Path(filename)
    if not path.exists():
        click.secho(f"Unable to find configuration: {filename}")

    config_files = configtools.file_list(filename)
    config_files.reverse()

    try:
        config = configparser.ConfigParser()
        config.read(config_files)
    except configparser.Error as e:
        print(e)
        sys.exit(2)

    return config


class AgentConfig:
    def __init__(self, cfg_name):
        self.cfg_name = cfg_name
        self.pbench_config = lookup_agent_configuration(self.cfg_name)
        try:
            self.agent = self.pbench_config["pbench-agent"]
            self.results = self.pbench_config["results"]
        except KeyError:
            raise exceptions.BadConfig()

    def get_agent(self):
        return self.agent

    def get_results(self):
        return self.results

    @property
    def installdir(self):
        return pathlib.Path(self.agent.get("install-dir", "/opt/pbench-agent"))

    @property
    def rundir(self):
        return pathlib.Path(self.agent.get("pbench_run", "/var/lib/pbench-agent"))
