import abc
import os
from pbench.agent import config
from pbench.common.utils import sysexit


class PbenchAgentCli(object, metaclass=abc.ABCMeta):
    def __init__(self, config=None, command_args=None):
        self.cfg = config
        self.command_args = command_args
        self.config = None

    @abc.abstractmethod
    def run(self):
        pass

    def main(self):
        self.get_config()
        self.run()

    def get_config(self):
        """Check for and read the configuration file"""
        if self.cfg:
            if not os.path.exists(self.cfg):
                print("Unable to determine configuration file")
                sysexit()
        else:
            if os.environ.get("CONFIG") is not None:
                self.cfg = os.environ.get("CONFIG")
            if os.environ.get("_PBENCH_AGENT_CONFIG") is not None:
                self.cfg = os.environ.get("_PBENCH_AGENT_CONFIG")

        self.config = config.PbenchAgentConfig(self.cfg)


def get_config():
    """Determine if we are running the agent or the server"""
    if os.environ.get("_PBENCH_SERVER_CONFIG"):
        return "_PBENCH_SERVER_CONFIG"
    elif os.environ.get("_PBENCH_AGENT_CONFIG"):
        return "_PBENCH_AGENT_CONFIG"
    else:
        raise Exception("Unable to determine environment")
