import configparser
import errno
import os
import pathlib

import click

from pbench import configtools
from pbench.lib.agent import exceptions
from pbench.lib.agent.constants import AGENT_PATH
from pbench.lib.agent.utils import sysexit

AGENT_DEBUG = os.environ.get("AGENT_DEBUG", "False")


def lookup_agent_configuration(filename=None):
    """Return config file PATH"""
    if filename is None:
        pbench_config = os.environ.get("_PBENCH_AGENT_CONFIG", None)
        if pbench_config is None:
            # pbench is not always invoked with -C or --config or the
            # _PBENCH_AGENT_CONFIG environment variable set. Since we
            # really need access to the config file to operate, and we
            # know the location of that config file
            # we check to see if that exists before declaring a problem.
            filename = os.path.join(AGENT_PATH, "config/pbench-agent-default.cfg")
        else:
            filename = pbench_config

    path = pathlib.Path(filename)
    if not path.exists():
        click.secho(f"Unable to find configuration: {filename}")
        sysexit()

    config_files = configtools.file_list(filename)
    config_files.reverse()

    try:
        config = configparser.ConfigParser()
        config.read(config_files)
    except configparser.Error as e:
        raise e
    except IOError as err:
        if err.errno == errno.ENOENT:
            raise exceptions.ConfigFileNotFound()
        if err.errno == errno.EACCES:
            raise exceptions.ConfigFileAccessDenied()
        raise

    return config


class AgentConfig:
    def __init__(self, cfg_name=None):
        self.cfg_name = cfg_name
        self.pbench_config = lookup_agent_configuration(self.cfg_name)
        try:
            self.agent = self.pbench_config["pbench-agent"]
        except KeyError:
            raise exceptions.BadConfig()

        try:
            self.results = self.pbench_config["results"]
        except KeyError:
            self.results = {}

    def get_agent(self):
        """Return the agent section"""
        return self.agent

    def get_results(self):
        """Return the results section"""
        return self.results

    @property
    def rundir(self):
        """Return the pbench run_dir"""
        return self.agent.get("run_dir", "/var/lib/pbench-agent")

    @property
    def installdir(self):
        """Return the pbench install-dir"""
        return self.agent.get("install-dir", "/opt/pbench-agent")

    @property
    def logdir(self):
        """Return the pbench log_dir"""
        return self.agent.get("pbench_log", None)
