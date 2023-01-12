import click

from pbench.cli import compose_options, options_callback


def common_options(f):
    """Option for agent configuration"""

    options = [
        click.option(
            "-C",
            "--config",
            required=True,
            envvar="_PBENCH_AGENT_CONFIG",
            type=click.Path(exists=True, readable=True),
            callback=options_callback,
            expose_value=False,
            help=(
                "Path to a pbench-agent configuration file (defaults to the "
                "'_PBENCH_AGENT_CONFIG' environment variable, if defined)"
            ),
        )
    ]

    return compose_options(f, options)
