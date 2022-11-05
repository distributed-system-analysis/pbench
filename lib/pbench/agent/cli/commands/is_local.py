import click

from pbench.agent.utils import LocalRemoteHost


@click.command()
@click.argument("host")
def main(host):
    """
    Determine whether host is a representation of `localhost`.

    If this logic cannot absolutely identify the host as an alias for the local
    system, then it will report "remote".

    Returns 0 for "local", 1 for "remote", or 2 for a parameter error.
    \f

    Args:
        host: An IP address or hostname
    """
    try:
        res = LocalRemoteHost().is_local(host)
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2
    else:
        rv = 0 if res else 1

    click.get_current_context().exit(rv)
