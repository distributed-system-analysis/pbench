from pathlib import Path

import click

from pbench.agent.base import BaseCommand
from pbench.agent.results import CopyResultTb
from pbench.cli import CliContext, pass_cli_context
from pbench.cli.agent.commands.results.results_options import results_common_options
from pbench.cli.agent.options import common_options
from pbench.common.utils import md5sum


class ResultsPush(BaseCommand):
    def __init__(self, context: CliContext):
        super().__init__(context)

    def execute(self) -> int:
        tarball_len, tarball_md5 = md5sum(self.context.result_tb_name)
        crt = CopyResultTb(
            self.context.controller,
            self.context.result_tb_name,
            tarball_len,
            tarball_md5,
            self.config,
            self.logger,
        )
        crt.copy_result_tb(self.context.token, self.context.access)
        return 0


@click.command(name="pbench-results-push")
@common_options
@results_common_options
@click.argument("controller")
@click.argument(
    "result_tb_name",
    type=click.Path(
        path_type=Path,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
)
@pass_cli_context
def main(
    context: CliContext,
    controller: str,
    result_tb_name: str,
    token: str,
    access: str,
):
    """Push a result tar ball to the configured Pbench server.

    \b
    CONTROLLER is the name of the controlling node.
    RESULT_TB_NAME is the path to the result tar ball.
    \f
    (This docstring will be printed as the help text for this command;
    the backslash-escaped letters are formatting directives; this
    parenthetical text will not appear in the help output.)
    """
    context.controller = controller
    context.result_tb_name = result_tb_name
    context.token = token
    context.access = access

    try:
        rv = ResultsPush(context).execute()
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 1

    click.get_current_context().exit(rv)
