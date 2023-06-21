from http import HTTPStatus
from pathlib import Path
from typing import List

import click

from pbench.agent.base import BaseCommand
from pbench.agent.results import CopyResult
from pbench.cli import CliContext, pass_cli_context, sort_click_command_parameters
from pbench.cli.agent.commands.results.results_options import results_common_options
from pbench.cli.agent.options import common_options
from pbench.common.utils import md5sum


class ResultsPush(BaseCommand):
    def __init__(self, context: CliContext):
        super().__init__(context)

    def execute(self) -> int:
        tarball = Path(self.context.result_tb_name)
        _, tarball_md5 = md5sum(tarball)
        crt = CopyResult.cli_create(self.context, self.config, self.logger)
        res = crt.push(tarball, tarball_md5)

        if res.ok and self.context.relay:
            click.echo(f"RELAY {tarball.name}: {res.url}")

        # success
        if res.status_code == HTTPStatus.CREATED:
            return 0

        try:
            msg = res.json()["message"]
        except Exception:
            msg = res.text if res.text else res.reason

        # dup or other unexpected but non-error status
        if res.ok:
            click.echo(msg, err=True)
            return 0

        click.echo(
            f"HTTP Error status: {res.status_code}, message: {msg}",
            err=True,
        )
        return 1


@sort_click_command_parameters
@click.command(name="pbench-results-push")
@common_options
@results_common_options
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
    result_tb_name: str,
    token: str,
    access: str,
    metadata: List,
    server: str,
    relay: str,
):
    """Push a result tar ball to the configured Pbench server.

    \b
    RESULT_TB_NAME is the path to the result tar ball.
    \f
    (This docstring will be printed as the help text for this command;
    the backslash-escaped letters are formatting directives; this
    parenthetical text will not appear in the help output.)
    """
    clk_ctx = click.get_current_context()

    context.result_tb_name = result_tb_name
    context.token = token
    context.access = access
    context.metadata = metadata
    context.server = server
    context.relay = relay

    if relay and server:
        click.echo("Cannot use both relay and Pbench Server destination.", err=True)
        clk_ctx.exit(2)

    try:
        rv = ResultsPush(context).execute()
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 1

    click.get_current_context().exit(rv)
