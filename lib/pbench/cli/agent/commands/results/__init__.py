import os
import shutil
import sys
import tempfile

import click

from pbench.agent.base import BaseCommand
from pbench.agent.results import (
    MakeResultTb,
    CopyResultTb,
    FileUploadError,
)
from pbench.cli.agent import pass_cli_context
from pbench.cli.agent.options import common_options
from pbench.common.exceptions import BadMDLogFormat
from pbench.common.logger import get_pbench_logger


class MoveResults(BaseCommand):
    """
        TODO:  This is latent code -- it is currently unused and largely
            untested, intended to implement a future tool to replace
            pbench-make-result-tb and/or pbench-move-results.
    """

    def __init__(self, context: click.Context):
        super().__init__(context)

    def execute(self) -> int:
        logger = get_pbench_logger("pbench-agent", self.config)

        temp_dir = tempfile.mkdtemp(
            dir=self.config.pbench_tmp, prefix="pbench-move-results."
        )

        runs_copied = 0
        failures = 0
        no_of_tb = 0

        for dirent in self.config.pbench_run.iterdir():
            if not dirent.is_dir():
                continue
            if dirent.name.startswith("tools-") or dirent.name == "tmp":
                continue

            no_of_tb += 1
            result_dir = dirent

            try:
                mrt = MakeResultTb(result_dir, temp_dir, self.config, logger)
            except FileNotFoundError as e:
                logger.error("File Not Found Error, {}", e)
                continue
            except NotADirectoryError as e:
                logger.error("Bad Directory, {}", e)
                continue

            try:
                result_tb_name = mrt.make_result_tb()
            except BadMDLogFormat as e:
                logger.warning("Bad Metadata.log file encountered, {}", e)
                failures += 1
                continue
            except FileNotFoundError as e:
                logger.debug("File Not Found error, {}", e)
                failures += 1
                continue
            except RuntimeError as e:
                logger.warning("Unexpected Error encountered, {}", e)
                failures += 1
                continue
            except Exception as e:
                logger.debug("Unexpected Error occurred, {}", e)
                failures += 1
                continue

            try:
                crt = CopyResultTb(
                    self.context.controller, result_tb_name, self.config, logger
                )
            except FileNotFoundError as e:
                logger.error("File Not Found error, {}", e)
                failures += 1
                continue

            try:
                crt.copy_result_tb(self.context.token)
            except (FileUploadError, RuntimeError) as e:
                logger.error("Error uploading a file, {}", e)
                failures += 1
                continue

            try:
                # We always remove the constructed tar ball, regardless of success
                # or failure, since we keep the result directory below on failure.
                os.remove(result_tb_name)
            except OSError:
                logger.error("Failed to remove {}", result_tb_name)
                failures += 1
                continue

            try:
                shutil.rmtree(result_dir)
            except OSError:
                logger.error("Failed to remove the {} directory hierarchy", result_dir)
                failures += 1
                continue

            runs_copied += 1

        logger.info(
            "Status: Total no. of tarballs {}, Successfully moved {}, Encountered {} failures",
            no_of_tb,
            runs_copied,
            failures,
        )

        return 0


@click.command()
@common_options
@click.option(
    "--controller",
    required=True,
    envvar="_pbench_full_hostname",
    prompt=False,
    help="Controller name",
)
@click.option(
    "--user", prompt=False, help="Pbench user (Obsolete)",
)
@click.option(
    "--token",
    required=True,
    prompt=True,
    envvar="PBENCH_ACCESS_TOKEN",
    help="pbench server authentication token (will prompt if unspecified)",
)
@click.option(
    "--prefix", help="Pbench prefix (Obsolete)",
)
@click.option(
    "--xz-single-threaded", help="Use single threaded compression (Obsolete)",
)
@click.option(
    "--show-server", help="pbench server where tarball will be moved (Not implemented)",
)
@pass_cli_context
def pmr(
    context: click.Context,
    controller: str,
    user: str,
    token: str,
    prefix: str,
    xz_single_threaded: str,
    show_server: str,
):
    """
        TODO:  This is latent code -- it is currently unused and largely
            untested, intended to implement a future tool to replace
            pbench-make-result-tb and/or pbench-move-results.
    """
    PROG = "pmr"
    context.controller = controller
    context.token = token

    if user:
        print(f"{PROG}: Option --user is no longer being used", file=sys.stderr)
    if prefix:
        print(f"{PROG}: Option --prefix is no longer being used", file=sys.stderr)
    if xz_single_threaded:
        print(f"{PROG}: Option --xz-single-threaded is ignored", file=sys.stderr)
    if show_server:
        print(f"{PROG}: Option --show-server is ignored", file=sys.stderr)

    try:
        rv = MoveResults(context).execute()
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 1

    click.get_current_context().exit(rv)
