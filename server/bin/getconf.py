#!/usr/bin/env python3

import sys
from pbench import configtools

if __name__ == "__main__":
    opts, args = configtools.parse_args(
        configtools.options,
        usage="Usage: getconf.py [options] <item>|-a <section> [<section> ...]",
    )
    conf, files = configtools.init(opts, "_PBENCH_SERVER_CONFIG")
    status = configtools.main(conf, args, opts, files)
    sys.exit(status)
