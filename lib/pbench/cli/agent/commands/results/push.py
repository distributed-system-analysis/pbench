import click

from pbench.agent.base import BaseCommand
from pbench.agent.results import CopyResultTb
from pbench.cli.agent import pass_cli_context
from pbench.cli.agent.options import common_options
from pbench.common.logger import get_pbench_logger


class ResultsPush(BaseCommand):
    def __init__(self, context: click.Context):
        super().__init__(context)

    def execute(self) -> int:
        logger = get_pbench_logger("pbench-agent", self.config)
        crt = CopyResultTb(
            self.context.controller, self.context.result_tb_name, self.config, logger
        )
        crt.copy_result_tb(self.context.token)
        return 0


@click.command()
@common_options
@click.option(
    "--token",
    required=True,
    prompt=True,
    envvar="PBENCH_ACCESS_TOKEN",
    help="pbench server authentication token (will prompt if unspecified)",
)
@click.argument("controller")
@click.argument(
    "result_tb_name",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@pass_cli_context
def main(
    context: click.Context, controller: str, result_tb_name: str, token: str,
):
    """Push a results tarball to the Pbench server.

        \b
        CONTROLLER is the name of the controlling node.
        RESULT_TB_NAME is the path to the results tarball.
        \f
        (This docstring will be printed as the help text for this command;
        the backslash-escaped letters are formatting directives; this
        parenthetical text will not appear in the help output.)
    """
    context.controller = controller
    context.result_tb_name = result_tb_name
    context.token = token

    try:
        rv = ResultsPush(context).execute()
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 1

    click.get_current_context().exit(rv)
