#!/usr/bin/env python3
# -*- mode: python -*-

import os
import sys
import json

from argparse import ArgumentParser

# from socket import gethostname
from pbench import PbenchConfig
from pbench.common.exceptions import BadConfig

# from pbench.server.existence import Existence

if __name__ != "__main__":
    sys.exit(1)

_prog = os.path.basename(sys.argv[0])
if _prog.endswith(".py"):
    _prog = _prog[:-3]


parser = ArgumentParser(_prog)
parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
parser.add_argument(
    "-n",
    "--name",
    dest="name",
    required=True,
    help="Specify name of tarball its status",
)
parser.add_argument(
    "--script",
    dest="script",
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
parser.add_argument(
    "--controller", dest="controller", required=True, help="The tarball's controller"
)
parser.add_argument(
    "--tstat", dest="tbstatus", required=True, help="The tarball's status"
)
parser.add_argument(
    "--op", dest="operation", required=True, help="The tarball's operation"
)
parsed = parser.parse_args()

try:
    config = PbenchConfig(parsed.cfg_name)
except BadConfig as e:
    print("{}: {}".format(_prog, e), file=sys.stderr)
    sys.exit(1)
"""
print(
    "\n\nstatus\n\nname = ",
    parsed.name,
    "\nscript-name = ",
    parsed.script,
    "\ncontroller = ",
    parsed.controller,
    "\ntbstatus = ",
    parsed.tbstatus,
    "\ntbts = ",
    parsed.operation,
)

"""

jsonfile = "/home/riya/tarstat.json"

tardict = {}
tardict[parsed.name] = {
    "name": parsed.name,
    "controller": parsed.controller,
    "operator": parsed.script,
    "operation": parsed.operation,
    "status": parsed.tbstatus,
    "information": "None",
}

# print("tardict === ", tardict, "     type === ", type(tardict))
dumpdata = json.dumps(tardict, indent=4)
with open(jsonfile) as json_file:
    loaddata = json.load(json_file)
# for tbstat in loaddata['Tb-status']:
#    print(tbstat['name'])
temp = loaddata["Tb-status"]
temp.append(tardict)
dumpdata1 = json.dumps(tardict, indent=4)

if os.path.exists(jsonfile):
    with open(jsonfile, "w") as fp:
        json.dump(loaddata, fp, indent=4)

print("\n\n")
"""
hostname = gethostname()

existence = Existence(config, parsed.name, parsed.script, parsed.controller, parsed.tbstatus, parsed.operation, hostname=hostname)
existence.init_report_template()
try:
    existence.post_status(parsed.timestamp)
except Exception:
    status = 1
else:
    status = 0
"""
status = 0
sys.exit(status)
