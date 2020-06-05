#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench Re-Index

Re-index all data for a given date range, "YYYY-MM-DD" to "YYYY-MM-DD".

The process of re-indexing first looks to see which INDEXED, TO-INDEX-TOOL,
and WONT-INDEX* symlinks exist in the given date range, and moves them to
TO-RE-INDEX.

NOTE: this interface is intended to be used interactively, this is NOT a
service that runs as a cronjob.  NO RE-INDEXING STEPS SHOULD BE AUTOMATED
AT THIS POINT.
"""

import sys
import os
import re

# import shutil
from pathlib import Path
from datetime import datetime
from argparse import ArgumentParser

from pbench import BadConfig
import pbench.server
from pbench.server import PbenchServerConfig


_NAME_ = "pbench-reindex"

tb_pat_r = (
    r"\S+_(\d\d\d\d)[._-](\d\d)[._-](\d\d)[T_](\d\d)[._:](\d\d)[._:](\d\d)\.tar\.xz"
)
tb_pat = re.compile(tb_pat_r)


def reindex(controller_name, tb_name, archive_p, incoming_p, dry_run=False):
    """reindex - re-index the given tar ball name.

    This method is responsible for finding the current symlink to the tar ball
    and moving it to the TO-RE-INDEX directory, creating that directory if
    it does not exist.
    """
    assert tb_name.endswith(".tar.xz"), f"invalid tar ball name, '{tb_name}'"

    if not (incoming_p / controller_name / tb_name[:-7]).exists():
        # Can't re-index tar balls that are not unpacked
        return (controller_name, tb_name, "not-unpacked", "")

    # Construct the controller path object used throughout the rest of this
    # method.
    controller_p = archive_p / controller_name
    # Construct the target path to which all tar ball symlinks will be moved.
    newpath = controller_p.joinpath("TO-RE-INDEX", tb_name)

    paths = []
    _linkdirs = ("TO-INDEX-TOOL", "INDEXED")
    for linkname_p in controller_p.glob(f"*/{tb_name}"):
        # Consider all existing tar ball symlinks
        if linkname_p.parent.name in ("TO-INDEX", "TO-RE-INDEX"):
            msg = (
                f"WARNING: {linkname_p.parent.name} link already exists for"
                f" {controller_p / tb_name}"
            )
            # Indicate no action taken, and exit early.
            return (controller_name, tb_name, "exists", msg)
        elif linkname_p.parent.name in _linkdirs:
            # One of the expected symlinks, add it for consideration below.
            paths.append(linkname_p)
        elif linkname_p.parent.name.startswith("WONT-INDEX"):
            # One of the expected WONT-INDEX* symlinks, also added for
            # consideration below.
            paths.append(linkname_p)
        # else:
        #   All other symlinks are not considered.

    if not paths:
        # No existing TO-INDEX or TO-RE-INDEX symlink, and no previous
        # indexing symlinks, exit early.
        return (controller_name, tb_name, "noop", "")

    if len(paths) > 1:
        # If we have more than one path then just flag this as a bad state
        # and exit early.
        return (controller_name, tb_name, "badstate", "")

    # At this point we are guaranteed to have only one path.
    assert len(paths) == 1, f"Logic bomb!  len(paths) ({len(paths)}) != 1"

    try:
        if not dry_run:
            paths[0].rename(newpath)
    except Exception as exc:
        msg = (
            f"WARNING: failed to rename symlink '{paths[0]}' to"
            f" '{newpath}', '{exc}'"
        )
        res = "error"
    else:
        msg = ""
        res = "succ"
    return (controller_name, tb_name, res, msg)


def gen_reindex_list(archive, oldest_dt, newest_dt):
    """gen_reindex_list - yield all controller/tarball names that should be
    re-indexed.
    """
    with os.scandir(archive) as archive_scan:
        # We are scanning the archive directory for all controller
        # sub-directories.
        for c_entry in archive_scan:
            if c_entry.name.startswith(".") and c_entry.is_dir(follow_symlinks=False):
                # Ignore the ".", "..", and any other ".*" subdirectories.
                continue
            if not c_entry.is_dir(follow_symlinks=False):
                # NOTE: the pbench-audit-server should pick up and flag this
                # unwanted condition.
                continue
            # We have a controller directory, now we scan the controller
            # directory for all tar balls.
            with os.scandir(c_entry.path) as controller_scan:
                for entry in controller_scan:
                    if not entry.is_file(follow_symlinks=False):
                        # Tar balls can only be files.
                        continue
                    if entry.name.startswith("."):
                        # Ignore any files starting with ".".
                        continue
                    match = tb_pat.fullmatch(entry.name)
                    if not match:
                        # Ignore any directory entries which do not match the
                        # tar ball pattern.  Such entries should be flagged by
                        # the server audit process.
                        continue
                    # Turn the pattern components of the match into a datetime
                    # object.
                    try:
                        tb_dt = datetime(
                            int(match.group(1)),
                            int(match.group(2)),
                            int(match.group(3)),
                        )
                    except ValueError:
                        # Tar ball has a bad date timestamp, the server audit
                        # process should flag those.
                        continue
                    if tb_dt < oldest_dt or newest_dt < tb_dt:
                        # This tar ball is outside the given range, ignore it.
                        continue
                    # Finally, we have a tar ball that is in the date range
                    yield c_entry.name, entry.name


def main(options):
    if not options.cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable",
            file=sys.stderr,
        )
        return 1

    try:
        config = PbenchServerConfig(options.cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 2

    try:
        archive_p = Path(config.ARCHIVE).resolve(strict=True)
    except FileNotFoundError:
        print(
            f"The configured ARCHIVE directory, {config.ARCHIVE}, does not exist",
            file=sys.stderr,
        )
        return 3

    if not archive_p.is_dir():
        print(
            f"The configured ARCHIVE directory, {config.ARCHIVE}, is not a valid directory",
            file=sys.stderr,
        )
        return 4

    try:
        incoming_p = Path(config.INCOMING).resolve(strict=True)
    except FileNotFoundError:
        print(
            f"The configured INCOMING directory, {config.INCOMING}, does not exist",
            file=sys.stderr,
        )
        return 5

    if not incoming_p.is_dir():
        print(
            f"The configured INCOMING directory, {config.INCOMING}, is not a valid directory",
            file=sys.stderr,
        )
        return 6

    _fmt = "%Y-%m-%d"
    try:
        oldest_dt = datetime.strptime(options.oldest, _fmt)
        newest_dt = datetime.strptime(options.newest, _fmt)
    except Exception as exc:
        print(
            f"Invalid time range, {options.oldest} to {options.newest}, "
            f"'{exc}', expected time range values in the form YYYY-MM-DD",
            file=sys.stderr,
        )
        return 7
    else:
        if newest_dt < oldest_dt:
            # For convenience, swap oldest and newest dates that are reversed.
            oldest_dt, newest_dt = newest_dt, oldest_dt

    print(f"Re-indexing tar balls in the range {oldest_dt} to {newest_dt}")

    actions = []
    start = pbench.server._time()
    for _val in gen_reindex_list(archive_p, oldest_dt, newest_dt):
        controller_name, tb_name = _val
        act_set = reindex(
            controller_name, tb_name, archive_p, incoming_p, options.dry_run
        )
        actions.append(act_set)
    end = pbench.server._time()

    for act_set in sorted(actions):
        print(f"{act_set!r}")

    print(f"Run-time: {start} {end} {end - start}")
    return 0


if __name__ == "__main__":
    parser = ArgumentParser(f"Usage: {_NAME_} [--config <path-to-config-file>]")
    parser.add_argument(
        "-C",
        "--config",
        dest="cfg_name",
        default=os.environ.get("_PBENCH_SERVER_CONFIG"),
        help="Specify config file",
    )
    parser.add_argument(
        "-D",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Perform a dry-run only",
    )
    parser.add_argument(
        "oldest", help="Oldest date of the range of tar balls to re-index"
    )
    parser.add_argument(
        "newest", help="Newest date of the range of tar balls to re-index"
    )
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
