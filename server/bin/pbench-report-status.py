#!/usr/bin/env python3
# -*- mode: python -*-

import sys, os
if __name__ != '__main__':
    sys.exit(1)

_prog = os.path.basename(sys.argv[0])
if _prog.endswith('.py'):
    _prog = _prog[:-3]

from argparse import ArgumentParser

parser = ArgumentParser(_prog)
parser.add_argument(
    "-C", "--config", dest="cfg_name",
    help="Specify config file")
parser.set_defaults(cfg_name = os.environ.get("CONFIG"))
parser.add_argument(
    "-n", "--name", dest="name", required=True,
    help="Specify name of program reporting its status")
parser.add_argument(
    "-t", "--timestamp", dest="timestamp", required=True,
    help="The timestamp that should be associated with the file to index,"
        " takes the form run-<yyyy>-<mm>-<dd>T<HH>:<MM>:<SS>-<TZ>")
parser.add_argument(
    "-T", "--type", dest="doctype", required=True,
    help="The type of report document to index, one of status|error")
parser.add_argument(
    "file_to_index", nargs=1,
    help="The file containing the report to index")
parsed = parser.parse_args()

from pbench import init_report_template, report_status, PbenchConfig, \
    BadConfig, get_es, get_pbench_logger, PbenchTemplates

try:
    config = PbenchConfig(parsed.cfg_name)
except BadConfig as e:
    print("{}: {}".format(_prog, e), file=sys.stderr)
    sys.exit(1)

logger = get_pbench_logger(_prog, config)
es, idx_prefix = init_report_template(config, logger)
status = report_status(es, logger, config.LOGSDIR, idx_prefix,
        parsed.name, parsed.timestamp, parsed.doctype,
        parsed.file_to_index[0])
sys.exit(status)
