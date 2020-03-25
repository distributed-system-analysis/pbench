#!/usr/bin/env python3
# -*- mode: python -*-

import os
import sys
from argparse import ArgumentParser

# Export all the expected pbench config file attributes for the
# existing shell scripts.  This maintains the single-source-of-
# truth for those definitions in the PbenchConfig class, but
# still accessible to all pbench bash shell scripts.
from pbench import BadConfig, PbenchConfig

if __name__ != "__main__":
    sys.exit(1)


_NAME_ = "pbench-base.py"

parser = ArgumentParser(_NAME_)
parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
parser.add_argument(
    "prog", metavar="PROG", type=str, nargs=1, help="the program name of the caller"
)
parser.add_argument(
    "args", metavar="args", type=str, nargs="*", help="program arguments"
)
parsed, _ = parser.parse_known_args()

_prog = os.path.basename(parsed.prog[0])
_dir = os.path.dirname(parsed.prog[0])

if not parsed.cfg_name:
    # pbench-base.py is not always invoked with -C or --config or the _PBENCH_SERVER_CONFIG
    # environment variable set.  Since we really need access to the config
    # file to operate, and we know the relative location of that config file,
    # we check to see if that exists before declaring a problem.
    config_name = os.path.join(
        os.path.dirname(_dir), "lib", "config", "pbench-server.cfg"
    )
    if not os.path.exists(config_name):
        print(
            "{}: No config file specified: set _PBENCH_SERVER_CONFIG env variable or use"
            " --config <file> on the command line".format(_prog),
            file=sys.stderr,
        )
        sys.exit(1)
else:
    config_name = parsed.cfg_name


try:
    config = PbenchConfig(config_name)
except BadConfig as e:
    print("{}: {} (config file {})".format(_prog, e, config_name), file=sys.stderr)
    sys.exit(1)

# Exclude the "files" and "conf" attributes from being exported
vars = sorted(
    [
        key
        for key in config.__dict__.keys()
        if key not in ("files", "conf", "timestamp", "_unittests", "get")
    ]
)
for att in vars:
    try:
        os.environ[att] = getattr(config, att)
    except AttributeError:
        print(
            '{}: Missing internal pbench attribute, "{}", in'
            " configuration".format(_prog, att),
            file=sys.stderr,
        )
        sys.exit(1)

if config._unittests:
    os.environ["_PBENCH_SERVER_TEST"] = "1"

cmd = "{}.sh".format(sys.argv[1])
args = [cmd] + sys.argv[2:]
os.execv(cmd, args)
