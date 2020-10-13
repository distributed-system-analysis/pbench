"""
pbench-clear-results
"""
import shutil
import sys

import click

from pbench.cli.agent import pass_cli_context
from pbench.agent.base import BaseCommand
from pbench.cli.agent.options import common_options


class ResultsClear(BaseCommand):
    """Clear files and directories other than stuff that start
    with tmp and start with tools
    """

    def __init__(self, context):
        super().__init__(context)

    def execute(self):
        try:
            for path in self.pbench_run.iterdir():
                # NOTE WELL: we remove each entry explicitly using the full
                # pbench_run path just in case some bug inadvertently places
                # us in the wrong directory.
                if not str(path.name).startswith(("tmp", "tools")):
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
            return 0
        except Exception as ex:
            self.logger.warn(
                "Unable to cleanup the '%s' directory: %s", self.pbench_run, ex
            )
            return 1


@click.command(help="clear all tools or filter by name of group")
@common_options
@pass_cli_context
def main(ctxt):
    status = ResultsClear(ctxt).execute()
    sys.exit(status)
