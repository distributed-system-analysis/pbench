#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench Tar Ball Stats

Scan through the ARCHIVE hierarchy for tar balls and report statistics from the
tar ball names and their controller names.
"""

import collections
import locale
import os
import re
import sys

from argparse import ArgumentParser, Namespace
from datetime import datetime

import pbench


_NAME_ = "pbench-tarball-stats"

tb_pat = re.compile(
    r"\S+_(\d\d\d\d)[._-](\d\d)[._-](\d\d)[T_](\d\d)[._:](\d\d)[._:](\d\d)\.tar\.xz"
)

TarBallInfo = collections.namedtuple("TarBallInfo", ["ctrl", "tb", "dt", "stat"])


def gen_tar_balls(archive: str) -> TarBallInfo:
    """Traverse the given ARCHIVE hierarchy looking tar balls, generating
    TarBallInfo tuples containing information about the tar balls found.

    The tuple contains: (
        controller name,
        tar ball name,
        datetime derived from the tar ball name (
            not the file system's modification time stamp),
        the "stat" object for that file
    )

    If we find a file in a controller directory that does not match the
    expected tar ball file name pattern, and is not a tar ball .md5 file,
    we STILL generated a tuple for that file but with None for the datetime
    of that tuple.
    """
    with os.scandir(archive) as archive_scan:
        for c_entry in archive_scan:
            if c_entry.name.startswith(".") or not c_entry.is_dir(
                follow_symlinks=False
            ):
                continue
            # We have a controller directory.
            with os.scandir(c_entry.path) as controller_scan:
                for entry in controller_scan:
                    if entry.name.startswith(".") or not entry.is_file(
                        follow_symlinks=False
                    ):
                        continue
                    match = tb_pat.fullmatch(entry.name)
                    if match:
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
                    elif entry.name.endswith(".md5"):
                        continue
                    else:
                        tb_dt = None
                    yield TarBallInfo(
                        ctrl=c_entry.name, tb=entry.name, dt=tb_dt, stat=entry.stat()
                    )


def get_sat_name(ctrl: str):
    """Return the satellite name from the controller directory string, where
    "-INT-" is returned if there isn't one.
    """
    parts = ctrl.split("::", 1)
    return "-INT-" if len(parts) == 1 else parts[0]


def report_by_bucket(buckets: dict):
    """Print reports for the provided dictionary of buckets, where the name of
    the bucket is the key, and each bucket is a list of TarBallInfo objects.
    """
    for bucket_name, bucket_list in sorted(buckets.items()):
        satellites = collections.Counter()
        count = len(bucket_list)
        print(f"{bucket_name}: {count:7n}", end="")
        for item in bucket_list:
            satellites[get_sat_name(item.ctrl)] += 1
        for name, total in sorted(satellites.items()):
            pct = (total / count) * 100.0
            print(f" ({name} {pct:0.02f}%)", end="")
        print("")


def stringify_name_total_pairs(kv: dict) -> str:
    """String-ify a dictionary `name`: `total` pairs, returning a comma
    separated string of the values.
    """
    pairs = [f"{name} {total:n}" for name, total in sorted(kv.items())]
    return ", ".join(pairs)


def main(options: Namespace) -> int:
    """Generate a report for the existing tar balls in the ARCHIVE directory.

    The report includes a break down by satellite server, good and bad tar
    balls (defined by having a proper time stamp in the name), and finally
    broken down by year and then by month.

    Returns 0 on success, 2 for any configuration errors.
    """
    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
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

    archive_p = os.path.realpath(config.ARCHIVE)
    if not archive_p:
        print(
            f"The configured ARCHIVE directory, {config.ARCHIVE}, does not exist",
            file=sys.stderr,
        )
        return 2
    if not os.path.isdir(archive_p):
        print(
            f"The configured ARCHIVE directory, {config.ARCHIVE}, is not a valid directory",
            file=sys.stderr,
        )
        return 2

    invalid_cnt = 0
    invalid_size = 0
    invalid = collections.defaultdict(list)

    good_cnt = 0
    good_size = 0
    good = collections.defaultdict(list)

    by_year = collections.defaultdict(list)
    by_month = collections.defaultdict(list)

    start = pbench._time()

    gen = gen_tar_balls(archive_p)

    satellites_tb = collections.Counter()
    for tb_rec in gen:
        if tb_rec.dt is None:
            invalid[tb_rec.ctrl].append(tb_rec)
            invalid_cnt += 1
            invalid_size += tb_rec.stat.st_size
        else:
            good[tb_rec.ctrl].append(tb_rec)
            good_cnt += 1
            good_size += tb_rec.stat.st_size
            satellites_tb[get_sat_name(tb_rec.ctrl)] += 1
            year = tb_rec.dt.year
            by_year[year].append(tb_rec)
            month = tb_rec.dt.month
            ym = f"{year:4d}-{month:02d}"
            by_month[ym].append(tb_rec)

    time_sec = pbench._time() - start

    print(f"Took {time_sec:0.2f} seconds")

    print(f"{len(invalid.keys()):18n} controllers with bad tar balls")
    print(f"{invalid_cnt:18n} bad tar balls, total count")
    print(f"{invalid_size:18n} bad tar balls, total size")

    print(f"{len(good.keys()):18n} controllers with good tar balls", end="")
    if good:
        satellites_ctrl = collections.Counter()
        for good_ctrl in good.keys():
            satellites_ctrl[get_sat_name(good_ctrl)] += 1
        print(f" ({stringify_name_total_pairs(satellites_ctrl)})")
    else:
        print("")
    print(f"{good_cnt:18n} good tar balls, total count", end="")
    if good:
        print(f" ({stringify_name_total_pairs(satellites_tb)})")
    else:
        print("")
    print(f"{good_size:18n} good tar balls, total size")

    report_by_bucket(by_year)
    report_by_bucket(by_month)

    return 0


if __name__ == "__main__":
    parser = ArgumentParser(f"Usage: {_NAME_} [--config <path-to-config-file>]")
    parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
    parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
