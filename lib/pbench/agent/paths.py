import pathlib
import sys

from pbench.agent.config import AgentConfig
from pbench.agent.utils import init_wrapper
from pbench.agent import fs
from pbench.agent.logger import logger


class Paths:
    def __init__(self, config=None):
        """Pbench administrative methods"""
        self.config = AgentConfig(config)

        init_wrapper()

    def config_activate(self, configfile):
        """
        copy the configuration file to the destination

        :param configfile: pbench agent configuration file
        """
        try:
            dest = pathlib.Path(AgentConfig(configfile).installdir, "config")
            if not dest.exists():
                # silently fail if pbench-ageht is not configured properly
                sys.exit(1)
            fs.copyfile(configfile, dest.joinpath("pbench-agent.cfg"))
        except Exception as ex:
            logger.error("Failed to copy configuration file %s: %s", configfile, ex)
            sys.exit(1)

    def config_ssh(self, keyfile):
        """
        Install the ssh private key file to allow pbench to move/copy results to the server.

        :param keyfile: ssh id_rsa file
        """
        try:
            user = self.config.user
            group = self.config.group
            dest = pathlib.Path(self.config.installdir, "id_rsa")
            print(dest)

            fs.copyfile(keyfile, dest, owner=(user, group))
        except Exception as ex:
            logger.error("Failed to copy ssh key %s: %s", keyfile, ex)
            sys.exit(1)

    def cleanup(self):
        """Remove files in the rundir"""
        try:
            path = pathlib.Path(self.config.rundir)
            logger.info("Cleaning up %s", path)

            # dont do anything if directory exists or directory is empty
            if not path.exists() or not any(path.iterdir()):
                sys.exit(1)

            fs.removetree(path)
        except Exception as ex:
            logger.error("Failed to cleanup %s: %s", self.config.rundir, ex)
            sys.exit(1)
