#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench Tar Ball Stats

Scan through the ARCHIVE hierarchy for tar balls and report statistics from the
tar ball names and their controller names.  See the Jinja2 report template for
what is included.
"""

import collections
import locale
import os
import re
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta

import jinja2
import pbench

_NAME_ = "pbench-tarball-stats"

tb_pat = re.compile(pbench.TAR_BALL_NAME_W_TAR_PAT_S)

TarBallInfo = collections.namedtuple("TarBallInfo", ["ctrl", "tb", "dt", "stat"])
TarBallStats = collections.namedtuple("TarBallStats", ["ctrls", "count", "size"])


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
    we STILL generate a tuple for that file but with None for the datetime
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
    "main" is returned if there isn't one.
    """
    parts = ctrl.split("::", 1)
    return "main" if len(parts) == 1 else parts[0]


_sevendays = timedelta(days=7)


def week_end(dt: datetime) -> str:
    """Return a string representing the week ending date of the given datetime
    object.
    """
    week_end = dt - timedelta(days=dt.isoweekday()) + _sevendays
    return f"{week_end:%Y-%m-%d}"


def transform_buckets(buckets: dict, sat_names: list, now: datetime, kind: str):
    """Transform a given bucket to calculate the % tar balls by the origin
    server.
    """
    if kind == "y":
        now_s = f"{now:%Y}"
    elif kind == "m":
        now_s = f"{now:%Y-%m}"
    else:
        assert kind == "w", f"error unexpected kind value, {kind!r}"
        now_s = week_end(now)
    twomonths = timedelta(days=60)
    new_buckets = {}
    for bucket_name, bucket_list in sorted(buckets.items()):
        if kind == "w":
            bucket_dt = datetime.strptime(bucket_name, "%Y-%m-%d")
            if bucket_dt + twomonths < now:
                continue
        satellites = collections.Counter()
        count = len(bucket_list)
        for item in bucket_list:
            satellites[get_sat_name(item.ctrl)] += 1
        sats_pct = {}
        # Ensure all known satellite names have a default of 0.00%.
        for name in sat_names:
            sats_pct[name] = 0.0
        for name, total in sorted(satellites.items()):
            pct = (total / count) * 100.0
            sats_pct[name] = pct
        new_buckets[bucket_name] = dict(
            count=count, sats_pct=sats_pct, partial=(now_s == bucket_name)
        )
    return new_buckets


# Jinja2 template for the report.  The following variables are required:
#
#   time_sec      - How long (in seconds) it took to find all the tar balls
#   good          - named tuple
#     .count      - # of good tar balls
#     .size       - size (in bytes) of all good tar balls combined
#     .ctrls      - dictionary of controller names mapped to counts of tar
#                   balls from a given origin server
#   server_origin - dictionary of pbench servers (main and satellites) names
#                   mapped to counts of tar balls that originated there
#   bad           - named tuple
#     .count      - # of bad tar balls
#     .size       - size (in bytes) of all bad tar balls combined
#     .ctrls      - dictionary of controllers with bad tar balls
#   by_year       - dictionary mapping counts of tar balls for each given
#                   year generated, with mappings per satellite server
#   by_month      - same as by_year, just "by month"
#   by_week       - list of dictionaries of weekly mappings, similar to by_year
#                   and by_month but with data for the weeks of the most recent
#                   two months, where we use the ISO week definition which
#                   starts on a Monday and ends on a Sunday.
#
# Each partial year, month, and week are marked with a capital 'P' to indicate
# it as such, where "partial" is determined by considering the date the report
# was created.
#
report_tmpl = """Summary Statistics for Tar Balls on {{ now.strftime("%Y-%m-%d") }} (external data only):

    Took {{ "{:0.2f}".format(time_sec) }} seconds to find all tar balls.

    Good Tar Balls:
        {{ "{:18n}".format(good.count) }} count
        {% if good.count > 0 %}
        {{ "{:>18s}".format(good.size|humanize_naturalsize) }} size

        By Server Origin:
        {% for name, value in server_origin.items()|sort %}
        {{ "{:18n}".format(value) }} {% if name == "main" %}{{ name }} pbench server{% else %}"{{ name }}" pbench satellite server{% endif +%}
        {% endfor %}

        Controller Counts:
        {{ "{:18n}".format(good.ctrls.keys()|length) }} controllers
        {% for name, value in satellites.items()|sort %}
        {{ "{:18n}".format(value) }} {% if name == "main" %}{{ name }} pbench server{% else %}"{{ name }}" pbench satellite server{% endif +%}
        {% endfor %}
        {% endif %}

    {% if bad.count > 0 %}
    Bad Tar Balls:
        {{ "{:18n}".format(bad.ctrls.keys()|length) }} controllers
        {{ "{:18n}".format(bad.count) }} count
        {{ "{:>18s}".format(bad.size|humanize_naturalsize) }} size

    {% endif %}
{% if server_origin.keys()|length > 0 %}
Tar Ball Counts broken down by weeks for most recent 2 months (with satellite percentages):

Week Ending  Total Count{% for name in server_origin.keys()|sort %}   {{ "{0:>7s}".format(name) }}{% endfor +%}
{% for name,value in by_week.items()|sort(reverse=True) %}
{{ "{0:<10s}".format(name) }} {% if value.partial %}P{% else %} {% endif +%} {{ "{:11n}".format(value.count) }}{% for name in server_origin.keys()|sort %}   {{ "{:6.2f}%".format(value.sats_pct[name]) }}{% endfor +%}
{% endfor %}

Tar Ball Counts broken down by Year (with satellite percentages):

Year         Total Count{% for name in server_origin.keys()|sort %}   {{ "{0:>7s}".format(name) }}{% endfor +%}
{% for name,value in by_year.items()|sort(reverse=True) %}
{{ "{0:<10s}".format(name) }} {% if value.partial %}P{% else %} {% endif +%} {{ "{:11n}".format(value.count) }}{% for name in server_origin.keys()|sort %}   {{ "{:6.2f}%".format(value.sats_pct[name]) }}{% endfor +%}
{% endfor %}

Tar Ball Counts broken down by Month (with satellite percentages):

Month        Total Count{% for name in server_origin.keys()|sort %}   {{ "{0:>7s}".format(name) }}{% endfor +%}
{% for name,value in by_month.items()|sort(reverse=True) %}
{{ "{0:<10s}".format(name) }} {% if value.partial %}P{% else %} {% endif +%} {{ "{:11n}".format(value.count) }}{% for name in server_origin.keys()|sort %}   {{ "{:6.2f}%".format(value.sats_pct[name]) }}{% endfor +%}
{% endfor %}
{% endif %}"""


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

    invalid = collections.defaultdict(list)
    invalid_cnt = 0
    invalid_size = 0

    good = collections.defaultdict(list)
    good_cnt = 0
    good_size = 0

    by_year = collections.defaultdict(list)
    by_month = collections.defaultdict(list)
    by_week = collections.defaultdict(list)

    start = pbench._time()

    now = datetime.utcfromtimestamp(start)

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
            by_year[str(tb_rec.dt.year)].append(tb_rec)
            ym = f"{tb_rec.dt.year:4d}-{tb_rec.dt.month:02d}"
            by_month[ym].append(tb_rec)
            by_week[week_end(tb_rec.dt)].append(tb_rec)

    satellites_ctrl = collections.Counter()
    if good:
        for good_ctrl in good.keys():
            satellites_ctrl[get_sat_name(good_ctrl)] += 1

    time_sec = pbench._time() - start

    env = jinja2.Environment(
        extensions=["jinja2_humanize_extension.HumanizeExtension"],
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tmpl = env.from_string(report_tmpl)
    print(
        tmpl.render(
            now=now,
            time_sec=time_sec,
            good=TarBallStats(count=good_cnt, size=good_size, ctrls=good),
            bad=TarBallStats(count=invalid_cnt, size=invalid_size, ctrls=invalid),
            server_origin=satellites_tb,
            satellites=satellites_ctrl,
            by_year=transform_buckets(by_year, satellites_tb.keys(), now, "y"),
            by_month=transform_buckets(by_month, satellites_tb.keys(), now, "m"),
            by_week=transform_buckets(by_week, satellites_tb.keys(), now, "w"),
        )
    )

    return 0


if __name__ == "__main__":
    parser = ArgumentParser(f"Usage: {_NAME_} [--config <path-to-config-file>]")
    parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
    parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
