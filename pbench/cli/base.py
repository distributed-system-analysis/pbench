import abc
import logging
import os
import subprocess
import sys

from pbench.lib.common import PBENCH_SERVER_DIR

LOG = logging.getLogger(__name__)


class App(object):
    def __init__(self, context, command_args):
        self.command_args = context
        self.subcommand_args = command_args
        self.config = None


class PbenchCli(App, metaclass=abc.ABCMeta):  # noqa:E999
    SCRIPT_NAME = None

    @abc.abstractmethod
    def run(self):
        pass

    def init_config(self):
        config = self.subcommand_args.get("config")
        if not config:
            # command is not always invoked with -C or --config or the _PBENCH_SERVER_CONFIG
            # environment variable set.  Since we really need access to the config
            # file to operate, and we know the relative location of that config file,
            # # we check to see if that exists before declaring a problem.
            self.config = os.path.join(
                PBENCH_SERVER_DIR, "lib", "config", "pbench-server.cfg"
            )
            if not os.path.exists(self.config):
                print(
                    "{}: No config file specified: set _PBENCH_SERVER_CONFIG env variable or use"
                    " --config <file> on the command line".format(
                        self.subcommand_args.get("prog")
                    ),
                    file=sys.stderr,
                )
                sys.exit(1)
            else:
                self.config = config

    def main(self):
        self.init_config()
        self.run()


def shell_execute(command, stdin=None):
    """execute shell script with error handling"""
    exitcode = 0
    output = []
    try:
        output = subprocess.check_output(
            command, stdin=False, shell=True, universal_newlines=True
        ).strip()
    except Exception:
        exitcode = -1
        LOG.error("exec command '%s' error:\n ", command, exc_info=True)

    return exitcode, output
