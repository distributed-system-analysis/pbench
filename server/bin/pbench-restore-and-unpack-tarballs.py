#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench Restore & Unpack Tar Balls

The goal is to find all tar balls that are in the backup tree and restore them
to the archive tree, unpacking as appropriate (left to the unpack process to
see if the tar ball is not too old), marking them as being already backed up.

The general algorithm is:

  1. Find all the tar balls on the backup drive

  2. Sort them by the date in the tar ball from newest to oldest

  3. For each tar ball

     a. Check if tar ball exists in archive tree, if so, skip

     b. Copy tar ball and .md5 to archive tree and run md5sum check

        * Creating the controller directory if it doesn't already exist

     c. Create symlink to tar ball in BACKED-UP directory

        * Creating the BACKED-UP directory if it doesn't already exist

     d. Create symlink to tar ball in TO-RE-UNPACK directory

        * Creating the TO-RE-UNPACK directory if it doesn't already exist
"""

import os
import re
import subprocess
import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

import pbench


_NAME_ = "pbench-restore-and-unpack-tarballs"

md5_suffix_len = len(".md5")

tb_pat_r = r"\S+_(\d\d\d\d)[._-](\d\d)[._-](\d\d)[T_](\d\d)[._:](\d\d)[._:](\d\d)\.tar\.xz\.md5"
tb_pat = re.compile(tb_pat_r)

report_tb_fmt = (
    "\nFile {combined:d} of {cnt:d} ({restored:d} restored,"
    " {existing:d} existing, so far), {state}: {tb}\n"
)


def gen_list(backup):
    """Traverse the given BACKUP hierarchy looking for all tar balls that have
    a .md5 file.
    """
    with os.scandir(backup) as backup_scan:
        for c_entry in backup_scan:
            if c_entry.name.startswith("."):
                continue
            if not c_entry.is_dir(follow_symlinks=False):
                continue
            # We have a controller directory.
            with os.scandir(c_entry.path) as controller_scan:
                for entry in controller_scan:
                    if entry.name.startswith("."):
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    match = tb_pat.fullmatch(entry.name)
                    if not match:
                        continue
                    # Turn the pattern components of the match into a datetime
                    # object.
                    tb_dt = datetime(
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3)),
                        int(match.group(4)),
                        int(match.group(5)),
                        int(match.group(6)),
                    )
                    tb = Path(entry.path[:-md5_suffix_len])
                    if not tb.exists():
                        raise Exception(
                            f"Tar ball .md5, '{entry.path}', does not have"
                            f" an associated tar ball, '{tb}'"
                        )
                    yield tb_dt, c_entry.name, tb


def escape_quotes(string):
    """Escape single and double quotes in a string suitable for use in a shell
    command.

    Returns the string with the quotes escaped.
    """
    return re.sub("(['\"])", r"\\\1", string)


def main(options):
    if not options.cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable",
            file=sys.stderr,
        )
        return 2

    try:
        config = pbench.PbenchConfig(options.cfg_name)
    except pbench.BadConfig as e:
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 2

    try:
        archive_p = Path(config.ARCHIVE).resolve(strict=True)
    except Exception as e:
        print(
            f"{_NAME_}: ERROR: could not resolve configured ARCHIVE directory,"
            f" {config.ARCHIVE}: {e}",
            file=sys.stderr,
        )
        return 2

    if not archive_p.is_dir():
        print(
            f"{_NAME_}: ERROR: The configured ARCHIVE directory, {archive_p},"
            " is not a valid directory",
            file=sys.stderr,
        )
        return 2

    backup = config.conf.get("pbench-server", "pbench-backup-dir")
    try:
        backup_p = Path(backup).resolve(strict=True)
    except Exception as e:
        print(
            f"{_NAME_}: ERROR: could not resolve the configured"
            f" pbench-backup-dir directory, {backup}: {e}",
            file=sys.stderr,
        )
        return 2

    if not backup_p.is_dir():
        print(
            f"{_NAME_}: ERROR: The configured pbench-backup-dir directory,"
            f" {backup}, is not a valid directory",
            file=sys.stderr,
        )
        return 2

    start = pbench._time()

    print(
        f"Restoring tar balls from backup volume, {backup} (started at: {start})",
        flush=True,
    )

    tbs_unsorted = list(gen_list(backup_p))
    tbs_cnt = len(tbs_unsorted)

    mid = pbench._time()

    print(
        f"Considering {tbs_cnt:d} tar balls from backup volume,"
        f" {backup} (at: {mid}, elapsed: {mid - start:0.2f})",
        flush=True,
    )

    tbs_left = tbs_cnt
    tbs_existing = 0
    tbs_restored = 0
    tbs_sorted = sorted(tbs_unsorted, reverse=True)
    ctrl_created = {}
    for tb_dt, ctrl, tb in tbs_sorted:
        try:
            a_tb = archive_p / ctrl / tb.name
            tbs_left -= 1

            if a_tb.exists():
                tbs_existing += 1
                print(
                    report_tb_fmt.format(
                        state="exists",
                        combined=tbs_restored + tbs_existing,
                        restored=tbs_restored,
                        existing=tbs_existing,
                        cnt=tbs_cnt,
                        tb=a_tb,
                    ),
                    flush=True,
                )
                continue

            # Create controller directory if it doesn't exist
            ctrl_p = archive_p / ctrl
            try:
                if not options.dry_run:
                    ctrl_p.mkdir()
            except FileExistsError:
                pass
            else:
                if ctrl not in ctrl_created:
                    print(f"\nCreated controller directory, '{ctrl_p}'", flush=True)
                ctrl_created[ctrl] = True

            # Copy tar ball to archive tree, along with its .md5 ...
            cp_cmd = escape_quotes(f"cp -a {tb} {tb}.md5 {ctrl_p}/")
            print(f"\n{cp_cmd}", flush=True)
            if not options.dry_run:
                cp = subprocess.run(cp_cmd, shell=True, stderr=subprocess.STDOUT)
                if cp.returncode != 0:
                    print(
                        f"FAILURE: cp command: '{cp_cmd}': {cp.returncode}, {cp.stdout!r}",
                        file=sys.stderr,
                    )
                    return 1
            # ... and run md5sum check against it
            md5sum_cmd = escape_quotes(f"md5sum --check {a_tb}.md5")
            print(md5sum_cmd, flush=True)
            if not options.dry_run:
                # NOTE: we have to set the current working directory for the
                # md5sum --check command to the controller directory since the
                # contents of the .md5 file uses a relative file reference.
                cp = subprocess.run(
                    md5sum_cmd, shell=True, stderr=subprocess.STDOUT, cwd=ctrl_p
                )
                if cp.returncode != 0:
                    print(
                        f"FAILURE: md5sum command: '{md5sum_cmd}': {cp.returncode}, {cp.stdout!r}",
                        file=sys.stderr,
                    )
                    return 1

            # Create the symlink recording the tar ball is already backed up
            backed_up_dir = ctrl_p / "BACKED-UP"
            if not options.dry_run:
                backed_up_dir.mkdir(exist_ok=True)
            backed_up = backed_up_dir / tb.name
            print(f"ln -s {a_tb} {backed_up}", flush=True)
            if not options.dry_run:
                backed_up.symlink_to(a_tb)

            # Create the symlink requesting the tar ball be unpacked
            to_unpack_dir = ctrl_p / "TO-RE-UNPACK"
            if not options.dry_run:
                to_unpack_dir.mkdir(exist_ok=True)
            to_unpack = to_unpack_dir / tb.name
            print(f"ln -s {a_tb} {to_unpack}", flush=True)
            if not options.dry_run:
                to_unpack.symlink_to(a_tb)

            tbs_restored += 1

            print(
                report_tb_fmt.format(
                    state="restored",
                    combined=tbs_restored + tbs_existing,
                    restored=tbs_restored,
                    existing=tbs_existing,
                    cnt=tbs_cnt,
                    tb=a_tb,
                ),
                flush=True,
            )
        except Exception as exc:
            print(
                f"Exception while processing ({tb_dt!r}, {ctrl!r}, {tb!r}): {exc}",
                file=sys.stderr,
            )
            raise

    end = pbench._time()
    print(
        f"Restored {tbs_restored:d} tar balls from backup volume,"
        f" {backup} (ended at: {end}, elapsed: {end - start:0.2f})"
    )

    return 0


if __name__ == "__main__":
    parser = ArgumentParser(f"Usage: {_NAME_} [--config <path-to-config-file>]")
    parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
    parser.add_argument(
        "-D",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Perform a dry-run only",
    )
    parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
