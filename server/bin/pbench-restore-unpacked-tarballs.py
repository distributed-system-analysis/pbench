#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench Restore Unpacked Tar Balls

The goal is to find all tar balls that are in the backup tree and restore them,
unpacking as appropriate, where only tar balls within the age range are
re-unpacked.

The general algorithm is:

  1. Find all the tar balls on the backup drive

  2. Sort them by the date in the tar ball from newest to oldest

  3. For each tar ball

     a. Check if tar ball is within the age limit, if not, skip

     b. Check if tar ball exists unpacked in incoming tree, if so, skip

     c. Copy tar ball and .md5 from backup tree to a temporary directory

     d. Verify the md5sum of the tar ball, if it fails, remove copy

     e. Move to the re-unpack tree
"""

import os
import re
import subprocess
import sys
import tempfile
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

import pbench

_NAME_ = "pbench-restore-unpacked-tarballs"

md5_suffix_len = len(".md5")

tb_pat = re.compile(pbench.TAR_BALL_NAME_W_MD5_PAT_S)

report_tb_fmt = (
    "\nFile {combined:d} of {cnt:d} ({restored:d} restored,"
    " {existing:d} existing, so far), {state}: {tb}\n"
)


def gen_list(backup: Path, curr_dt: datetime, max_age: int):
    """Traverse the given BACKUP hierarchy looking for all tar balls that have
    a .md5 file.

    Args:
        backup : Path object for backup directory hierarchy
        curr_dt : Current datetime object to use for tar ball age comparison
        max_age : Age limit in number of days

    Yields:
        Tuples of (datetime, str, Path), which are the tar ball creation date,
        controller name, and Path object to the on-disk tar ball
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
                    ).replace(tzinfo=pbench.UTC)

                    # See if this tar ball has "aged" out.
                    timediff = curr_dt - tb_dt
                    if timediff.days > max_age:
                        continue

                    tb = Path(entry.path[:-md5_suffix_len])
                    if not tb.exists():
                        raise Exception(
                            f"Tar ball .md5, '{entry.path}', does not have"
                            f" an associated tar ball, '{tb}'"
                        )
                    yield tb_dt, c_entry.name, tb


def escape_quotes(string: str) -> str:
    """Escape single and double quotes in a string suitable for use in a shell
    command.

    Args:
        string : The string with quotes to be escaped

    Returns:
        The input string with the quotes escaped
    """
    return re.sub("(['\"])", r"\\\1", string)


def main(options) -> int:
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

    backup_p = pbench.get_conf_dir(_NAME_, config, "pbench-backup-dir")
    if backup_p is None:
        return 2

    incoming_p = pbench.get_conf_dir(_NAME_, config, "pbench-incoming-dir")
    if incoming_p is None:
        return 2

    re_unpack_p = pbench.get_conf_dir(_NAME_, config, "pbench-re-unpack-dir")
    if re_unpack_p is None:
        return 2

    tmp_p = pbench.get_conf_dir(_NAME_, config, "pbench-tmp-dir")
    if tmp_p is None:
        return 2

    # Fetch the configured maximum number of days a tar ball can remain
    # "unpacked" in the INCOMING tree.
    try:
        max_unpacked_age = config.conf.get("pbench-server", "max-unpacked-age")
    except Exception as e:
        print(
            f"{_NAME_}: ERROR: could not fetch the 'max-unpacked-age' option"
            f" from the 'pbench-server' section of the config file: {e}",
            file=sys.stderr,
        )
        return 2
    try:
        max_unpacked_age = int(max_unpacked_age)
    except Exception:
        print(
            f"{_NAME_}: ERROR: Bad maximum unpacked age, {max_unpacked_age}",
            file=sys.stderr,
        )
        return 2

    # Determine the proper time to use as a reference.
    start = pbench.utcnow()
    start_ts = start.strftime("%Y-%m-%dT%H:%M:%S-%Z")
    print(
        f"Restoring tar balls from backup volume, {backup_p} (started at: {start_ts})",
        flush=True,
    )

    tbs_unsorted = list(gen_list(backup_p, start, max_unpacked_age))
    tbs_cnt = len(tbs_unsorted)

    mid = pbench.utcnow()
    mid_ts = start.strftime("%Y-%m-%dT%H:%M:%S-%Z")
    print(
        f"Considering {tbs_cnt:d} tar balls from backup volume,"
        f" {backup_p} (at: {mid_ts}, elapsed: {(mid - start).total_seconds()})",
        flush=True,
    )

    tbs_left = tbs_cnt
    tbs_existing = 0
    tbs_restored = 0
    tbs_sorted = sorted(tbs_unsorted, reverse=True)
    ctrl_created = {}
    with tempfile.TemporaryDirectory(prefix="reunpack-", dir=tmp_p) as wrkdir:
        wrkdir_p = Path(wrkdir)
        for tb_dt, ctrl, tb in tbs_sorted:
            try:
                ctrl_p = incoming_p / ctrl
                i_tb = ctrl_p / tb.name[:-7]
                tbs_left -= 1

                if i_tb.exists():
                    tbs_existing += 1
                    print(
                        report_tb_fmt.format(
                            state="exists",
                            combined=tbs_restored + tbs_existing,
                            restored=tbs_restored,
                            existing=tbs_existing,
                            cnt=tbs_cnt,
                            tb=i_tb,
                        ),
                        flush=True,
                    )
                    continue

                # Copy tar ball to working directory, along with its .md5 ...
                cp_cmd = escape_quotes(f"cp -a {tb} {tb}.md5 {wrkdir_p}/")
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
                md5sum_cmd = escape_quotes(f"md5sum --check {tb.name}.md5")
                print(md5sum_cmd, flush=True)
                if not options.dry_run:
                    # NOTE: we have to set the current working directory for the
                    # md5sum --check command to the controller directory since
                    # the contents of the .md5 file uses a relative file
                    # reference.
                    cp = subprocess.run(
                        md5sum_cmd, shell=True, stderr=subprocess.STDOUT, cwd=wrkdir_p
                    )
                    if cp.returncode != 0:
                        print(
                            f"FAILURE: md5sum command: '{md5sum_cmd}':"
                            f" {cp.returncode}, {cp.stdout!r}",
                            file=sys.stderr,
                        )
                        return 1

                # Create controller directory if it doesn't exist
                ctrl_p = re_unpack_p / ctrl
                try:
                    if not options.dry_run:
                        ctrl_p.mkdir()
                except FileExistsError:
                    pass
                else:
                    if ctrl not in ctrl_created:
                        print(f"\nCreated controller directory, '{ctrl_p}'", flush=True)
                    ctrl_created[ctrl] = True

                # Move tar ball to re-unpack directory, along with its .md5 ...
                wtb = wrkdir_p / tb.name
                mv_cmd = escape_quotes(f"mv {wtb} {wtb}.md5 {ctrl_p}/")
                print(f"\n{mv_cmd}", flush=True)
                if not options.dry_run:
                    mv = subprocess.run(mv_cmd, shell=True, stderr=subprocess.STDOUT)
                    if mv.returncode != 0:
                        print(
                            f"FAILURE: mv command: '{mv_cmd}': {mv.returncode}, {mv.stdout!r}",
                            file=sys.stderr,
                        )
                        return 1

                tbs_restored += 1

                print(
                    report_tb_fmt.format(
                        state="restored",
                        combined=tbs_restored + tbs_existing,
                        restored=tbs_restored,
                        existing=tbs_existing,
                        cnt=tbs_cnt,
                        tb=i_tb,
                    ),
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"Exception while processing ({tb_dt!r}, {ctrl!r}, {tb!r}): {exc}",
                    file=sys.stderr,
                )
                raise

    end = pbench.utcnow()
    end_ts = start.strftime("%Y-%m-%dT%H:%M:%S-%Z")
    print(
        f"Restored {tbs_restored:d} tar balls from backup volume,"
        f" {backup_p} (ended at: {end_ts}, elapsed: {(end - start).total_seconds()})"
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
    try:
        status = main(parsed)
    except Exception as exc:
        print(f"{_NAME_}: INTERNAL ERROR - {exc}", file=sys.stderr)
        status = 1
    sys.exit(status)
