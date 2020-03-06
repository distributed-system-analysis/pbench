import abc
import logging
import os
import sys

LOG = logging.getLogger(__name__)

class PbenchCli(object):
    def __init__(self, context, command_args):
        self.command_args = context
        self.subcommes_args = command_args
        self.config = None

    def get_config(self):
        """Load the configuration file"""
        if os.environ.get("_PBENCH_AGENT_CONFIG"):
            self.config = os.environ.get("_PBENCH_AGENT_CONFIG")
        elif os.environ.get("_PBENCH_SERVER_CONFIG"):
            self.config = os.environ.get("_PBENCH_SERVER_CONFIG")
        elif self.command_args.obj.get("args")["config"] is not None:
            self.config = (self.command_args.obj.get("args")["config"])
        else:
            LOG.error("Unable to determine configuration file.")
            sys.exit(1)

        if not os.path.exists(self.config):
            LOG.error("Unable to find configuration file %s" % self.config)

class Base(PbenchCli, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def run(self):
        pass

    def main(self):
        self.get_config()
        self.run()

