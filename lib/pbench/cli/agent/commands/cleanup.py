import os
import sys

import click

from pbench.agent.utils import setup_logging
from pbench.agent.cleanup import CleanupCommand
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class Cleanup(CleanupCommand):
    def __init__(self, context):
        super(Cleanup, self).__init__(context)

        self.logger = setup_logging(name=os.path.basename(sys.argv[0]), logfile=self.pbench_log)
    
    def execute(self):
        return self.cleanup()

@click.command(help="")
@common_options
@pass_cli_context
def main(ctxt):
    status = Cleanup(ctxt).execute()
    sys.exit(status)