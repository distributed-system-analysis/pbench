import os
import shutil

from pbench.cli.base import PbenchAgentCli


class PbenchCleanup(PbenchAgentCli):
    def run(self):
        run_dir = self.config.get_pbench_run_dir()
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)
