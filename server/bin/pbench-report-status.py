#!/usr/bin/env python3
# -*- mode: python -*-

import sys

if __name__ != "__main__":
    sys.exit(1)

import os

_prog = os.path.basename(sys.argv[0])
if _prog.endswith(".py"):
    _prog = _prog[:-3]

from argparse import ArgumentParser

parser = ArgumentParser(_prog)
parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
parser.add_argument(
    "-n",
    "--name",
    dest="name",
    required=True,
    help="Specify name of program reporting its status",
)
parser.add_argument(
    "-t",
    "--timestamp",
    dest="timestamp",
    required=True,
    help="The timestamp that should be associated with the file to index,"
    " takes the form run-<yyyy>-<mm>-<dd>T<HH>:<MM>:<SS>-<TZ>",
)
parser.add_argument("-p", "--pid", dest="pid", required=True, help="The caller's pid")
parser.add_argument(
    "-g",
    "--gid",
    dest="group_id",
    required=False,
    help="The caller's group ID (optional)",
)
parser.add_argument(
    "-u",
    "--uid",
    dest="user_id",
    required=False,
    help="The caller's user ID (optional)",
)
parser.add_argument(
    "-T",
    "--type",
    dest="doctype",
    required=True,
    help="The type of report document to index, one of status|error",
)
parser.add_argument(
    "file_to_index", nargs=1, help="The file containing the report to index"
)
parsed = parser.parse_args()

from pbench import PbenchConfig, BadConfig

try:
    config = PbenchConfig(parsed.cfg_name)
except BadConfig as e:
    print("{}: {}".format(_prog, e), file=sys.stderr)
    sys.exit(1)

from pbench.report import Report
from socket import gethostname

hostname = gethostname()
pid = parsed.pid
group_id = parsed.group_id
user_id = parsed.user_id

report = Report(
    config, parsed.name, pid=pid, group_id=group_id, user_id=user_id, hostname=hostname
)
report.init_report_template()
try:
    report.post_status(parsed.timestamp, parsed.doctype, parsed.file_to_index[0])
except Exception:
    status = 1
else:
    status = 0
sys.exit(status)
