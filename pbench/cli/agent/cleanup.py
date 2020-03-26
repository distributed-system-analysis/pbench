import os
import pathlib
import shutil

from pbench.cli.base import PbenchAgentCli


class PbenchCleanup(PbenchAgentCli):
    def run(self):
        run_dir = self.config.get_pbench_run_dir()
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)


class PbenchCleanupTools(PbenchAgentCli):
    def run(self):
        run_dir = self.config.get_pbench_run_dir()
        if os.path.exists(run_dir):
            f = [
                f.name
                for f in pathlib.Path(run_dir).glob("*")
                if not f.name.startswith("tmp") and not f.name.startswith("tools")
            ]
            for x in f:
                pathlib.Path(run_dir).unlink()
