import os
import logging
import shutil

from pbench.cli.base import PbenchAgentCli
from pbench.common.utils import sysexit

LOG = logging.getLogger(__name__)


class PbenchConfigure(PbenchAgentCli):
    def run(self):
        install_dir = self.config.get_pbench_install_dir()
        if not os.path.exists(install_dir):
            print("{} does not exist".format(install_dir))
            sysexit()

        try:
            conf = "%s/config" % install_dir
            shutil.copy(self.cfg, conf)
        except Exception as ex:
            LOG.error("Failed to copy configuraiton file: %s", ex)
            sysexit()

        sysexit(0)


class PbenchSSHKey(PbenchAgentCli):
    def run(self):
        pbench_user = self.config.get_pbench_user()
        pbench_group = self.config.get_pbench_gorup()

        install_dir = self.config.get_pbench_install_dir()
        if not os.path.exists(install_dir):
            print("{} does not exist".format(install_dir))
            sysexit()

        keyfile = self.command_args["keyfile"]
        if not os.path.exists(keyfile):
            print("{} - keyfile does not exist".format(keyfile))
            sysexit()

        try:
            shutil.copy(keyfile, "%s/id_rsa" % install_dir)
            shutil.chown("%s/id_rsa" % install_dir, pbench_user, pbench_group)
            os.chmod("%s/id_rsa" % install_dir, 600)
        except Exception as ex:
            LOG.error(
                "Exception raised while running pbench-agent-config-ssh-key: %s ", ex
            )
            sysexit(3)

        sysexit(0)
