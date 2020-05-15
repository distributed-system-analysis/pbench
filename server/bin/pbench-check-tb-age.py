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
from pathlib import Path
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

    try:
        tb_path = Path(options.tb_path).resolve(strict=True)
    except FileNotFoundError:
        print(
            f"The Tarball Path, '{options.tb_path}', does not resolve to a real location"
        )
    else:
        tb_name = tb_path.name

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

    archivepath = config.ARCHIVE

    incoming = config.INCOMING
    try:
        incomingpath = incoming.resolve(strict=True)
    except FileNotFoundError:
        print(
            f"The configured INCOMING directory, {incoming}, does not exist",
            file=sys.stderr,
        )
        return 7
    else:
        if not incomingpath.is_dir():
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

    if not str(tb_path).startswith(str(archivepath)):
        print(f"Given tar ball, {tb_path}, not from the ARCHIVE tree", file=sys.stderr)
        return 12

    if not tb_path.exists():
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
        controller_p = tb_path.parent.name
        if Path(incomingpath, controller_p, tb_name, ".__pbench_keep__").is_file():
            ret_val = 0
        else:
            ret_val = 1
    else:
        ret_val = 0

    return ret_val


if __name__ == "__main__":
    prog = Path(sys.argv[0]).name
    parser = ArgumentParser(f"Usage: {prog} [--config <path-to-config-file>]")
    parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
    parser.add_argument("tb_path", help="Specify the full path of tar ball to check")
    parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
