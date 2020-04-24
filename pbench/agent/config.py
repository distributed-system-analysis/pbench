import configparser
import os
import pathlib
import sys

from pbench.common import configtools
from pbench.common import exceptions
from pbench.common.constants import AGENT_PATH
from pbench.agent.utils import error_out

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
            filename = os.path.join(AGENT_PATH, 
                "config/pbench-agent-default.cfg")
        else:
            filename = pbench_config            
    
    path = pathlib.Path(filename)
    if not path.exists():
        error_out(f"Unable to find configuration: {filename}")
    
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
    def __init__(self, cfg_name=None):
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