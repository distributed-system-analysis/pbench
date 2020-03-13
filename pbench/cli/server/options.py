import os


import click


def server_config_option(f):
    """Common pbench-server-* options"""
    f = click.option(
        "-C",
        "--config",
        "cfg_name",
        default=os.environ.get("_PBENCH_SERVER_CONFIG"),
        help="Specify configuration file",
    )(f)
    return f


def common_arguments(f):
    f = click.argument("args", metavar="args")(f)
    return f
