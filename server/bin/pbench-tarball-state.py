#!/usr/bin/env python3
# -*- mode: python -*-

import sys
if __name__ != '__main__':
    sys.exit(1)

import os
_prog = os.path.basename(sys.argv[0])
if _prog.endswith('.py'):
    _prog = _prog[:-3]

from argparse import ArgumentParser

parser = ArgumentParser(_prog)
parser.add_argument(
    "-C", "--config", dest="cfg_name",
    help="Specify config file")
parser.set_defaults(cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG"))
parser.add_argument(
    "-n", "--name", dest="name", required=True,
    help="Specify name of program reporting its status")
parser.add_argument(
    "-t", "--timestamp", dest="timestamp", required=True,
    help="The timestamp that should be associated with the file to index,"
        " takes the form run-<yyyy>-<mm>-<dd>T<HH>:<MM>:<SS>-<TZ>")
parser.add_argument(
    "--controller", dest="controller", required=True,
    help="The tarball's controller")
parser.add_argument(
    "--tstat", dest="tbstatus", required=True,
    help="The tarball's status")
parser.add_argument(
    "--tbts", dest="tarballts", required=True,
    help="The tarball's timestamp")
parsed = parser.parse_args()

from pbench import PbenchConfig, BadConfig

try:
    config = PbenchConfig(parsed.cfg_name)
except BadConfig as e:
    print("{}: {}".format(_prog, e), file=sys.stderr)
    sys.exit(1)

from pbench.existence import Existence
from socket import gethostname
hostname = gethostname()

existence = Existence(config, parsed.name, parsed.controller, parsed.tbstatus, parsed.tarballts, hostname=hostname)
existence.init_report_template()
try:
    existence.post_status(parsed.timestamp)
except Exception:
    status = 1
else:
    status = 0
sys.exit(status)
