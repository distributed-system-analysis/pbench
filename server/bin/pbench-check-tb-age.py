#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench Check TB Age

Return 0 if the given tar ball (full path) is within the configured maximum
age (specified in days), and return 1 if it is not.

A return value > 1 indicates some other error with the command.
"""

import sys
import os
import re
from datetime import datetime
from argparse import ArgumentParser
from configparser import NoOptionError

from pbench import BadConfig
from pbench.server import PbenchServerConfig


_NAME_ = "pbench-check-tb_age"

tb_pat_r = (
    r"\S+_(\d\d\d\d)[._-](\d\d)[._-](\d\d)[T_](\d\d)[._:](\d\d)[._:](\d\d)\.tar\.xz"
)
tb_pat = re.compile(tb_pat_r)


def main(options):
    if not options.tb_path:
        print(
            f"{_NAME_}: ERROR: No tar ball path specified", file=sys.stderr,
        )
        return 2
    tb_path = os.path.realpath(options.tb_path)
    tb_name = os.path.basename(tb_path)

    if not options.cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable",
            file=sys.stderr,
        )
        return 3

    try:
        config = PbenchServerConfig(options.cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 4

    archive = config.ARCHIVE
    archive_p = os.path.realpath(archive)

    if not archive_p:
        print(
            f"The configured ARCHIVE directory, {archive}, does not exist",
            file=sys.stderr,
        )
        return 5

    if not os.path.isdir(archive_p):
        print(
            f"The configured ARCHIVE directory, {archive}," " is not a valid directory",
            file=sys.stderr,
        )
        return 6

    incoming = config.INCOMING
    incoming_p = os.path.realpath(incoming)

    if not incoming_p:
        print(
            f"The configured INCOMING directory, {incoming}, does not exist",
            file=sys.stderr,
        )
        return 7

    if not os.path.isdir(incoming_p):
        print(
            f"The configured INCOMING directory, {incoming},"
            " is not a valid directory",
            file=sys.stderr,
        )
        return 8

    # Fetch the configured maximum number of days a tar can remain "unpacked"
    # in the INCOMING tree.
    try:
        max_unpacked_age = config.conf.get("pbench-server", "max-unpacked-age")
    except NoOptionError as e:
        print(f"{e}", file=sys.stderr)
        return 9
    try:
        max_unpacked_age = int(max_unpacked_age)
    except Exception:
        print(f"Bad maximum unpacked age, {max_unpacked_age}", file=sys.stderr)
        return 10

    # Check the unpacked directory name pattern.
    match = tb_pat.fullmatch(tb_name)
    if not match:
        print(f"Unrecognized tar ball name format, {tb_name}", file=sys.stderr)
        return 11

    if not tb_path.startswith(archive_p):
        print(f"Given tar ball, {tb_path}, not from the ARCHIVE tree", file=sys.stderr)
        return 12

    if not os.path.exists(tb_path):
        print(
            f"Given tar ball, {tb_path}, does not seem to exist in the ARCHIVE tree",
            file=sys.stderr,
        )
        return 13

    # Determine the proper time to use as a reference.
    if config._ref_datetime is not None:
        try:
            curr_dt = config._ref_datetime
        except Exception:
            # Ignore bad dates from test environment.
            curr_dt = datetime.utcnow()
    else:
        curr_dt = datetime.utcnow()

    # Turn the pattern components of the match into a datetime object.
    tb_dt = datetime(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4)),
        int(match.group(5)),
        int(match.group(6)),
    )

    # See if this unpacked tar ball directory has "aged" out.
    timediff = curr_dt - tb_dt
    if timediff.days > max_unpacked_age:
        # Finally, make one last check to see if this tar ball
        # directory should be kept regardless of aging out.
        controller_p = os.path.basename(os.path.dirname(tb_path))
        if os.path.isfile(
            os.path.join(incoming_p, controller_p, tb_name, ".__pbench_keep__")
        ):
            ret_val = 0
        else:
            ret_val = 1
    else:
        ret_val = 0

    return ret_val


if __name__ == "__main__":
    prog = os.path.basename(sys.argv[0])
    parser = ArgumentParser(f"Usage: {prog} [--config <path-to-config-file>]")
    parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
    parser.add_argument("tb_path", help="Specify the full path of tar ball to check")
    parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
