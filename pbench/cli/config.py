import sys

from pbench.cli.base import get_config
from pbench.lib import configtools


def main():
    opts, args = configtools.parse_args(
        configtools.options,
        usage="Usage: pbench-config [options] <item>|-a <section> [<section> ...]",
    )
    cfg = get_config()
    conf, files = configtools.init(opts, cfg)
    status = configtools.main(conf, args, opts, files)
    sys.exit(status)
