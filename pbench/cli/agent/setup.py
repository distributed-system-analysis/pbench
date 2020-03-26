import os
import shutil

from pbench.cli.base import PbenchAgentCli
from pbench.common.utils import sysexit


class PbenchConfigure(PbenchAgentCli):
    def run(self):
        install_dir = self.config.get_pbench_install_dir()
        if not os.path.exists(install_dir):
            print("{} does not exist".format(install_dir))
            sysexit()

        conf = "%s/config" % install_dir
        shutil.copy(self.cfg, conf)
