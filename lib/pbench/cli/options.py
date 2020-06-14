import click


#
# Default options
#
def pbench_agent_config(f):
    """Option for agent configuration"""
    return click.option(
        "-C",
        "--config",
        default="_PBENCH_AGENT_CONFIG",
        help=(
            "Path to a pbench-agent config. If provided pbench will load "
            "this config file first. By default is looking for config in "
            "'_PBENCH_AGENT_CONFIG' envrionment variable."
        ),
        type=click.Path(exists=True),
    )(f)
