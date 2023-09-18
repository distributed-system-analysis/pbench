import sys

import click

from pbench.cli import compose_options


def results_common_options(f):
    """Common options for results command"""

    def server_token_required(ctx, param, value):
        if not (ctx.params.get("relay") or "--help" in sys.argv[1:] or value):
            raise click.MissingParameter()
        return value

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
            "-b",
            "--brief",
            is_flag=True,
            default=False,
            help="Output bare relay manifest URIs",
        ),
        click.option(
            "-m",
            "--metadata",
            multiple=True,
            help=(
                "list of metadata keys to be sent on PUT."
                " Option may need to be specified multiple times for multiple values."
                " Format: key:value"
            ),
        ),
        click.option(
            "--server",
            help="Specify the Pbench Server as https://host[:port]",
        ),
        click.option(
            "--relay",
            help="Specify a relay server as http[s]://host[:port]",
        ),
        click.option(
            "--token",
            envvar="PBENCH_ACCESS_TOKEN",
            callback=server_token_required,
            help="pbench server authentication token",
        ),
    ]

    return compose_options(f, options)
