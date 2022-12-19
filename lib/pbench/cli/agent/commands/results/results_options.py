import click

from pbench.cli.agent import CliContext


def results_common_options(f):
    f = _results_options(f)
    return f


def _results_options(f):
    """Common option for results command"""

    def callback(ctx, _param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.config = value
        return value

    return click.option(
        "-a",
        "--access",
        default="private",
        show_default=True,
        type=click.Choice(["public", "private"], case_sensitive=False),
        help="pbench tarball access permission public/private (will prompt if unspecified)",
    )(f)
