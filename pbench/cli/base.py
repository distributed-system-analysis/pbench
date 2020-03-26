import abc
import os
import sys

from pbench.agent import config
from pbench.common.utils import sysexit


class PbenchAgentCli(object, metaclass=abc.ABCMeta):
    def __init__(self, config=None):
        self.config = None

    @abc.abstractmethod
    def run(self):
        pass

    def main(self):
        self.get_config()
        self.run()

    def get_config(self):
        pbench_config = os.environ.get("_PBENCH_AGENT_CONFIG")
        if pbench_config:
            if not os.path.exists(pbench_config):
                print("Unable to determine configuration file")
                sysexit()
            self.config = config.PbenchAgentConfig(pbench_config)
        else:
            print(
                "{}: No config file specified: set _PBENCH_AGENT_CONFIG env "
                "variable.".format(sys.argv[0])
            )
            sysexit()


def get_config():
    """Determine if we are running the agent or the server"""
    if os.environ.get("_PBENCH_SERVER_CONFIG"):
        return "_PBENCH_SERVER_CONFIG"
    elif os.environ.get("_PBENCH_AGENT_CONFIG"):
        return "_PBENCH_AGENT_CONFIG"
    else:
        raise Exception("Unable to determine environment")
