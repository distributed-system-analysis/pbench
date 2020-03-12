import abc
import logging
import os
import sys

LOG = logging.getLogger(__name__)


class PbenchCli(object):
    def __init__(self, context, command_args):
        self.command_args = context
        self.subcommand_args = command_args
        self.config = None

class Base(PbenchCli, metaclass=abc.ABCMeta):  # noqa:E999
    @abc.abstractmethod
    def run(self):
        pass

    def main(self):
        self.run()
