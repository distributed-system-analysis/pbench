"""
pbench-cleanup
"""

import click

from pbench.agent.base import BaseCommand
from pbench.cli.agent import pass_cli_context
from pbench.cli.agent.options import common_options
from pbench.agent.utils import run_command


class Cleanup(BaseCommand):
    def __init__(self, context):
        super().__init__(context)

    def execute(self):
        self.logger.warn(
            "%s deprecated, will be removed in future release in favor of pbench-clear-results",
            self.name,
        )
        try:
            run_command("pbench-clear-results", self.logger)
        except RuntimeError as e:
            self.logger.error(e)


@click.command()
@common_options
@pass_cli_context
def main(ctxt):
    Cleanup(ctxt).execute()
