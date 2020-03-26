import os
import pathlib

from pbench.cli.base import PbenchAgentCli
from pbench.common.utils import sysexit


class PbenchCleanupTools(PbenchAgentCli):
    def run(self):
        pbench_run_dir = self.config.get_pbench_run_dir()
        if not os.path.exists(pbench_run_dir):
            print("Unable to determine directory: {}".format(pbench_run_dir))
            sysexit()

        group = self.command_args["group"]
        name = self.command_args["name"]
        path = pathlib.Path(pbench_run_dir)

        path = pathlib.Path(pbench_run_dir)
        if path.exists():
            if name:
                self._remove(path, "tools-*/%s" % name)
            elif group:
                self._remove(path, "tools-%s/*" % group)
            else:
                self._remove(path, "tools-*/*")

    def _remove(self, path, tool):
        files = path.rglob(tool)
        for f in files:
            if f.exists() and f.is_file():
                f.unlink()
