from typing import Callable

import click

from pbench.cli import CliContext


def common_options(in_f: Callable) -> Callable:
    """
    This function can be used as a decorator for multiple server side CLI utilities,
    where it receives a click command decorated function as an argument and sets some
    common configuration options on the CLI, in this case pbench server configuration
    :param in_f: click command decorated function
    :return: function with common click options set
    """
    out_f = _pbench_server_config(in_f)
    return out_f


def _pbench_server_config(f: Callable) -> Callable:
    """Option for server configuration"""

    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.config = (
            value if value else "/opt/pbench-server/lib/config/pbench-server.cfg"
        )
        return value

    return click.option(
        "-C",
        "--config",
        required=False,
        envvar="_PBENCH_SERVER_CONFIG",
        type=click.Path(exists=True, readable=True),
        callback=callback,
        expose_value=False,
        help=(
            "Path to a pbench-server configuration file (defaults to the "
            "'_PBENCH_SERVER_CONFIG' environment variable, if defined)"
        ),
    )(f)
