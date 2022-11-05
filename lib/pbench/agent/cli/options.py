import click

from pbench.agent.cli import CliContext


def common_options(f):
    f = _pbench_agent_config(f)
    return f


def _pbench_agent_config(f):
    """Option for agent configuration"""

    def callback(ctx, _param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.config = value
        return value

    return click.option(
        "-C",
        "--config",
        required=True,
        envvar="_PBENCH_AGENT_CONFIG",
        type=click.Path(exists=True, readable=True),
        callback=callback,
        expose_value=False,
        help=(
            "Path to a pbench-agent configuration file (defaults to the "
            "'_PBENCH_AGENT_CONFIG' environment variable, if defined)"
        ),
    )(f)
