"""pbench-is-remote"""

import click

from pbench.agent.utils import LocalRemoteHost


@click.command()
@click.argument("host")
def main(host):
    try:
        res = LocalRemoteHost().is_remote(host)
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2
    else:
        rv = 0 if res else 1

    click.get_current_context().exit(rv)
