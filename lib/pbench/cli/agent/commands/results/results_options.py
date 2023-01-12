import click

from pbench.cli import compose_options


def results_common_options(f):
    """Common options for results command"""

    options = [
        click.option(
            "-a",
            "--access",
            default="private",
            show_default=True,
            type=click.Choice(["public", "private"], case_sensitive=False),
            help="pbench tarball access permission",
        ),
        click.option(
            "--token",
            required=True,
            envvar="PBENCH_ACCESS_TOKEN",
            prompt=False,
            help="pbench server authentication token",
        ),
    ]

    return compose_options(f, options)
