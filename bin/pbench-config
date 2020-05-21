#!/usr/bin/env python3

import os
import sys

from pbench.common import configtools


def get_pbench_config():
    """Determine if we are using agent or server."""
    agent_cfg = os.environ.get("_PBENCH_AGENT_CONFIG")
    server_cfg = os.environ.get("_PBENCH_SERVER_CONFIG")
    if agent_cfg:
        return "_PBENCH_AGENT_CONFIG"
    elif server_cfg:
        return "_PBENCH_SERVER_CONFIG"
    else:
        return sys.exit(1)


def main():
    opts, args = configtools.parse_args(
        configtools.options,
        usage="Usage: getconf.py [options] <item>|-a <section> [<section> ...]",
    )
    conf, files = configtools.init(opts, get_pbench_config())
    status = configtools.main(conf, args, opts, files)
    sys.exit(status)


if __name__ == "__main__":
    main()
