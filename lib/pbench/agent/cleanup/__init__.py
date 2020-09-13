import shutil

from pbench.agent.base import BaseCommand


class CleanupMixIn:
    def cleanup(self):
        self.logger.info("Cleaning up %s", self.pbench_run)
        if self.pbench_run.exists():
            for dir in self.pbench_run.iterdir():
                if dir.is_file():
                    dir.unlink()
                if dir.is_dir():
                    shutil.rmtree(dir)

class CleanupCommand(BaseCommand, CleanupMixIn):
    def __init__(self, context):
        super(CleanupCommand, self).__init__(context)
