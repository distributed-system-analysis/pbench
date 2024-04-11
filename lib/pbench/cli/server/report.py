from collections import defaultdict
import datetime
from operator import and_
from pathlib import Path
import re
import shutil
import time
from typing import Any, Iterator, Optional, Union

import click
import humanize
from sqlalchemy import cast, inspect, Row, select, text

from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup, Detail, Verify, Watch
from pbench.cli.server.options import common_options
from pbench.common.logger import get_pbench_logger
from pbench.server import BadConfig
from pbench.server.cache_manager import CacheManager
from pbench.server.database.database import Database
from pbench.server.database.models import TZDateTime
from pbench.server.database.models.audit import Audit, AuditStatus
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.index_map import IndexMap

# An arbitrary really big number
GINORMOUS = 2**64

# A similarly arbitrary big floating point number
GINORMOUS_FP = 1000000.0

# Number of bytes in a megabyte, coincidentally also a really big number
MEGABYTE_FP = 1000000.0

# SQL "chunk size"
SQL_CHUNK = 2000

# Translate datetime.datetime.month (1 - 12) into a name.
MONTHS = (
    "00",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

# Translate datetime.datetime.weekday() (0 - 6) into a name
DAYS_OF_WEEK = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

detailer: Optional[Detail] = None
watcher: Optional[Watch] = None
verifier: Optional[Verify] = None


class Comparator:
    def __init__(self, name: str, really_big: Union[int, float] = GINORMOUS):
        """Initialize a comparator

        Args:
            name: A name for the comparator
            really_big: An optional maximum value
        """
        self.name = name
        self.min = really_big
        self.min_name = None
        self.max = -really_big
        self.max_name = None

    def add(
        self,
        name: str,
        value: Union[int, float],
        max: Optional[Union[int, float]] = None,
    ):
        """Add a data point to the comparator

        Args:
            name: The name of the associated dataset
            value: The value of the datapoint
            max: [Optional] A second "maximum" value if adding a min/max pair
        """
        minv = value
        maxv = max if max is not None else value
        if minv < self.min:
            self.min = minv
            self.min_name = name
        if maxv > self.max:
            self.max = maxv
            self.max_name = name


def report_archive(tree: CacheManager):
    """Report archive statistics.

    Args:
        tree: a cache instance
    """

    watcher.update("inspecting archive")
    tarball_count = len(tree.datasets)
    tarball_size = 0
    tcomp = Comparator("tarball")
    usage = shutil.disk_usage(tree.archive_root)

    for tarball in tree.datasets.values():
        watcher.update(f"({tarball_count}) archive {tarball.name}")
        size = tarball.tarball_path.stat().st_size
        tarball_size += size
        tcomp.add(tarball.name, size)
    click.echo("Archive report:")
    click.echo(
        f"  ARCHIVE ({tree.archive_root}): {humanize.naturalsize(usage.total)}: {humanize.naturalsize(usage.used)} "
        f"used, {humanize.naturalsize(usage.free)} free"
    )
    click.echo(
        f"  {tarball_count:,d} tarballs consuming {humanize.naturalsize(tarball_size)}"
    )
    click.echo(
        f"  The smallest tarball is {humanize.naturalsize(tcomp.min)}, "
        f"{tcomp.min_name}"
    )
    click.echo(
        f"  The biggest tarball is {humanize.naturalsize(tcomp.max)}, "
        f"{tcomp.max_name}"
    )


def report_backup(tree: CacheManager):
    """Report tarball backup statistics.

    Args:
        tree: a cache instance
    """

    watcher.update("inspecting backups")
    backup_count = 0
    backup_size = 0
    usage = shutil.disk_usage(tree.backup_root)
    for tarball in tree.backup_root.glob("**/*.tar.xz"):
        watcher.update(f"({backup_count}) backup {Dataset.stem(tarball)}")
        backup_count += 1
        backup_size += tarball.stat().st_size

    click.echo("Backup report:")
    click.echo(
        f"  BACKUP ({tree.backup_root}): {humanize.naturalsize(usage.total)}: {humanize.naturalsize(usage.used)} "
        f"used, {humanize.naturalsize(usage.free)} free"
    )
    click.echo(
        f"  {backup_count:,d} tarballs consuming {humanize.naturalsize(backup_size)}"
    )


def report_cache(tree: CacheManager):
    """Report cache statistics.

    Args:
        tree: a cache instance
    """

    watcher.update("inspecting cache")
    cached_count = 0
    cached_size = 0
    lacks_size = 0
    lacks_tarpath = 0
    bad_size = 0
    found_metrics = False
    lacks_metrics = 0
    bad_metrics = 0
    unpacked_count = 0
    unpacked_multiple = 0
    stream_unpack_skipped = 0
    last_ref_errors = 0
    agecomp = Comparator("age", really_big=time.time() * 2.0)
    unpackcomp = Comparator("unpack")
    sizecomp = Comparator("size")
    compcomp = Comparator("compression")
    speedcomp = Comparator("speed", really_big=GINORMOUS_FP)
    streamcomp = Comparator("streaming", really_big=GINORMOUS_FP)

    rows = (
        Database.db_session.query(
            Dataset.name,
            Dataset.resource_id,
            Metadata.value["tarball-path"].as_string(),
            Metadata.value["unpacked-size"],
            Metadata.value["unpack-perf"],
        )
        .execution_options(stream_results=True)
        .outerjoin(
            Metadata,
            and_(Dataset.id == Metadata.dataset_ref, Metadata.key == "server"),
        )
        .yield_per(SQL_CHUNK)
    )

    for dsname, rid, tar, size, metrics in rows:
        watcher.update(f"({cached_count}) cache {dsname}")
        if tar:
            tarball = Path(tar)
            tarname = Dataset.stem(tarball)
        else:
            detailer.error(f"{dsname} doesn't have a 'server.tarball-path' metadata")
            lacks_tarpath += 1
            tarball = None
            tarname = dsname
        cache = Path(tree.cache_root / rid)
        if (cache / tarname).exists():
            cached_count += 1
            try:
                referenced = (cache / "last_ref").stat().st_mtime
            except Exception as e:
                detailer.error(f"{dsname} last ref access: {str(e)!r}")
                last_ref_errors += 1
            else:
                agecomp.add(dsname, referenced)
        if not size:
            detailer.error(f"{dsname} has no unpacked size")
            lacks_size += 1
        elif not isinstance(size, int):
            detailer.error(
                f"{dsname} has non-integer unpacked size "
                f"{size!r} ({type(size).__name__})"
            )
            bad_size += 1
        else:
            sizecomp.add(dsname, size)
            cached_size += size

            # Check compression ratios
            if tarball:
                tar_size = tarball.stat().st_size
                ratio = float(size - tar_size) / float(size)
                compcomp.add(dsname, ratio)
        if not metrics:
            # NOTE: message not error since nobody has this yet (noise)
            detailer.message(f"{dsname} has no unpack metrics")
            lacks_metrics += 1
        elif not isinstance(metrics, dict) or {"min", "max", "count"} - set(
            metrics.keys()
        ):
            detailer.error(
                f"{dsname} has bad unpack metrics "
                f"{metrics!r} ({type(metrics).__name__})"
            )
            bad_metrics += 1
        else:
            found_metrics = True
            unpacked_count += 1
            if metrics["count"] > 1:
                unpacked_multiple += 1
            unpackcomp.add(dsname, metrics["count"])
            speedcomp.add(dsname, metrics["min"], metrics["max"])
            if size:
                stream_fast = size / metrics["min"] / MEGABYTE_FP
                stream_slow = size / metrics["max"] / MEGABYTE_FP
                streamcomp.add(dsname, stream_slow, stream_fast)
            else:
                stream_unpack_skipped += 1
    oldest = datetime.datetime.fromtimestamp(agecomp.min, datetime.timezone.utc)
    newest = datetime.datetime.fromtimestamp(agecomp.max, datetime.timezone.utc)
    click.echo("Cache report:")
    click.echo(
        f"  {cached_count:,d} datasets currently unpacked, consuming "
        f"{humanize.naturalsize(cached_size)}"
    )
    click.echo(
        f"  {unpacked_count:,d} datasets have unpack metrics and "
        f"{unpacked_multiple} have been unpacked more than once."
    )
    if unpackcomp.max > 1 or verifier.verify:
        click.echo(
            f"  The most unpacked dataset has been unpacked {unpackcomp.max} times, "
            f"{unpackcomp.max_name}"
        )
    click.echo(
        "  The least recently used cache was referenced "
        f"{humanize.naturaldate(oldest)}, {agecomp.min_name}"
    )
    click.echo(
        "  The most recently used cache was referenced "
        f"{humanize.naturaldate(newest)}, {agecomp.max_name}"
    )
    click.echo(
        f"  The smallest cache is {humanize.naturalsize(sizecomp.min)}, "
        f"{sizecomp.min_name}"
    )
    click.echo(
        f"  The biggest cache is {humanize.naturalsize(sizecomp.max)}, "
        f"{sizecomp.max_name}"
    )
    click.echo(
        f"  The worst compression ratio is {compcomp.min:.3%}, " f"{compcomp.min_name}"
    )
    click.echo(
        f"  The best compression ratio is {compcomp.max:.3%}, " f"{compcomp.max_name}"
    )
    if found_metrics:
        click.echo(
            f"  The fastest cache unpack is {speedcomp.min:.3f} seconds, "
            f"{speedcomp.min_name}"
        )
        click.echo(
            f"  The slowest cache unpack is {speedcomp.max:.3f} seconds, "
            f"{speedcomp.max_name}"
        )
        click.echo(
            f"  The fastest cache unpack streaming rate is {streamcomp.max:.3f} Mb/second, "
            f"{streamcomp.max_name}"
        )
        click.echo(
            f"  The slowest cache unpack streaming rate is {streamcomp.min:.3f} Mb/second, "
            f"{streamcomp.min_name}"
        )
    if lacks_size or last_ref_errors or bad_size or verifier.verify:
        click.echo(
            f"  {lacks_size:,d} datasets have no unpacked size, "
            f"{last_ref_errors:,d} are missing reference timestamps, "
            f"{bad_size:,d} have bad size metadata"
        )
    if bad_metrics or verifier.verify:
        click.echo(f"  {bad_metrics:,d} have bad unpack metric data")
    if lacks_tarpath or verifier.verify:
        click.echo(
            f"  {lacks_tarpath} datasets are missing server.tarball-path metadata"
        )


def columnize(
    items: dict[int, int],
    width: int = 80,
    ifmt: str = "4d",
    cfmt: str = ">8,d",
    lookup: Optional[list[str]] = None,
):
    """Combine multiple outputs across a line to minimize vertical space

    Args:
        items: dictionary of items to report as "key: value"
        width: width of line to fill (default 80)
        ifmt: format string for key
        cfmt: format string for value
        lookup: list of string values to represent key
    """
    line = ""
    for item, count in sorted(items.items()):
        try:
            k = lookup[item] if lookup else item
        except Exception as e:
            click.echo(f"{item} from {lookup}: {str(e)!r}", err=True)
            k = str(item)
        add = f"    {k:{ifmt}}: {count:{cfmt}}"
        if len(line) + len(add) >= width:
            click.echo(line)
            line = add
        else:
            line += add
    if line:
        click.echo(line)


def summarize_dates(rows: Iterator[Row], width: int = 80):
    by_year = defaultdict(int)
    by_month = defaultdict(int)
    by_day = defaultdict(int)
    by_weekday = defaultdict(int)
    by_hour = defaultdict(int)

    day = datetime.datetime.now(datetime.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    month = day.replace(day=1)
    year = month.replace(month=1)
    week = day - datetime.timedelta(days=7)

    this_year = 0
    this_month = 0
    this_week = 0
    this_day = 0

    for row in rows:
        date: datetime.datetime = row[0]
        if not isinstance(date, datetime.datetime):
            detailer.message(f"Got non-datetime row {row}")
            continue
        by_year[date.year] += 1
        by_month[date.month] += 1
        by_day[date.day] += 1
        by_weekday[date.weekday()] += 1
        by_hour[date.hour] += 1

        if date >= year:
            this_year += 1
            if date >= month:
                this_month += 1
                if date >= week:
                    this_week += 1
                    if date >= day:
                        this_day += 1

    click.echo(f"  {this_year:,d} this year ({year:%Y})")
    click.echo(f"  {this_month:,d} this month ({month:%B %Y})")
    click.echo(f"  {this_week:,d} this week ({week:%B %d} to {day:%B %d})")
    click.echo(f"  {this_day:,d} today ({day:%d %B %Y})")

    click.echo(" Total by year:")
    columnize(by_year, width)
    click.echo(" Total by month of year:")
    columnize(by_month, width, ifmt="s", lookup=MONTHS)
    click.echo(" Total by day of month:")
    columnize(by_day, width, ifmt="02d")
    click.echo(" Total by day of week:")
    columnize(by_weekday, width, ifmt="s", lookup=DAYS_OF_WEEK)
    click.echo(" Total by hour of day:")
    columnize(by_hour, width, ifmt="02d")


def report_creation(options: dict[str, Any]):
    """Report dataset statistics by creation date"""

    watcher.update("analyzing upload patterns")

    rows = (
        Database.db_session.query(
            cast(Metadata.value["pbench", "date"].as_string(), TZDateTime)
        )
        .filter(Metadata.key == "metalog")
        .execution_options(stream_results=True)
        .yield_per(SQL_CHUNK)
    )
    click.echo("Dataset statistics by creation date:")
    summarize_dates(rows, options.get("width"))


def report_uploads(options: dict[str, Any]):
    """Report dataset statistics by upload date"""

    watcher.update("analyzing upload patterns")

    rows = (
        Database.db_session.query(Dataset.uploaded)
        .execution_options(stream_results=True)
        .yield_per(SQL_CHUNK)
    )
    click.echo("Dataset statistics by upload date:")
    summarize_dates(rows, options.get("width"))


def report_audit():
    """Report audit log statistics."""

    counter = 0
    events = 0
    unmatched_roots = set()
    unmatched_terminal = set()
    status = defaultdict(int)
    operations = defaultdict(int)
    objects = defaultdict(int)
    users = defaultdict(int)
    watcher.update("inspecting audit log")
    audit_logs = (
        Database.db_session.query(Audit)
        .execution_options(stream_results=True)
        .order_by(Audit.timestamp)
        .yield_per(SQL_CHUNK)
    )
    for audit in audit_logs:
        counter += 1
        watcher.update(f"[{counter}] inspecting {audit.id} -> {audit.timestamp}")
        status[audit.status.name] += 1
        if audit.status is AuditStatus.BEGIN:
            events += 1
            unmatched_roots.add(audit.id)
            operations[audit.name] += 1
            n = audit.user_name if audit.user_name else "<system>"
            users[n] += 1
            t = audit.object_type.name if audit.object_type else "<none>"
            objects[t] += 1
        else:
            try:
                unmatched_roots.remove(audit.root_id)
            except KeyError:
                detailer.error(f"audit {audit} has no matching `BEGIN`")
                unmatched_terminal.add(audit.id)

    click.echo("Audit logs:")
    click.echo(f"  {counter:,d} audit log rows for {events:,d} events")
    click.echo(
        f"  {len(unmatched_roots)} unterminated root rows, "
        f"{len(unmatched_terminal)} unmatched terminators"
    )
    click.echo("  Status summary:")
    for name, count in status.items():
        click.echo(f"    {name:>20s} {count:>10,d}")
    click.echo("  Operation summary:")
    for name, count in operations.items():
        click.echo(f"    {name:>20s} {count:>10,d}")
    click.echo("  Object type summary:")
    for name, count in objects.items():
        click.echo(f"    {name:>20s} {count:>10,d}")
    click.echo("  Users summary:")
    for name, count in users.items():
        click.echo(f"    {name:>20s} {count:>10,d}")


def report_sql():
    """Report the SQL table storage statistics"""

    watcher.update("inspecting SQL tables")
    table_count = 0
    row_count = 0
    row_size = 0
    click.echo("SQL storage report:")
    t_w = 20
    r_w = 10
    s_w = 10
    click.echo(f"  {'Table':<{t_w}} {'Rows':<{r_w}} {'Storage':<{s_w}}")
    click.echo(f"  {'':-<{t_w}} {'':-<{r_w}} {'':-<{s_w}}")
    for t in inspect(Database.db_session.get_bind()).get_table_names():
        table_count += 1
        (rows,) = next(
            Database.db_session.execute(statement=text(f"SELECT COUNT(*) FROM {t}"))
        )
        (size,) = next(
            Database.db_session.execute(
                statement=text("SELECT pg_total_relation_size(:table)"),
                params={"table": t},
            )
        )
        click.echo(f"  {t:<{t_w}} {rows:>{r_w},d} {humanize.naturalsize(size):>{s_w}}")
        row_count += rows
        row_size += size
    click.echo(
        f"  Total of {row_count:,d} rows in {table_count:,d} tables, consuming {humanize.naturalsize(row_size)}"
    )

    if not detailer:
        return

    watcher.update("inspecting index map details")
    record_count = 0
    roots = set()
    indices = set()
    root_size = 0
    index_size = 0

    query = select(IndexMap.root, IndexMap.index)
    for root, index in Database.db_session.execute(
        query, execution_options={"stream_results": True}
    ).yield_per(SQL_CHUNK):
        record_count += 1
        watcher.update(f"({record_count}: {root} -> {index}")
        roots.add(root)
        indices.add(index)
        root_size += len(root)
        index_size += len(index)
        unique_root_size = sum(len(r) for r in roots)
        unique_index_size = sum(len(i) for i in indices)

    detailer.message(
        f"{record_count:,d} indexmap records found with {len(indices):,d} indices "
        f"and {len(roots):,d} roots:"
    )
    detailer.message(
        f" {humanize.naturalsize(index_size)} for index names, "
        f"{humanize.naturalsize(root_size)} for root names"
    )
    detailer.message(
        f" deduped: {humanize.naturalsize(unique_index_size)} for index "
        f"names, {humanize.naturalsize(unique_root_size)} for root names"
    )


def report_states():
    """Report tarball operational states."""

    watcher.update("inspecting operational states")
    index_pattern: re.Pattern = re.compile(r"^(\d+):(.*)$")
    index_errors = defaultdict(int)
    index_messages = defaultdict(str)
    ops_anomalies = 0
    operations = defaultdict(lambda: defaultdict(int))
    rows = Database.db_session.execute(
        statement=text(
            "SELECT d.name, o.name, o.state, o.message FROM datasets AS d LEFT OUTER JOIN "
            "dataset_operations AS o ON o.dataset_ref = d.id"
        ),
        execution_options={"stream_results": True},
    ).yield_per(SQL_CHUNK)
    for dataset, operation, state, message in rows:
        watcher.update(f"inspecting {dataset}:{operation}")
        if operation is None:
            ops_anomalies += 1
            detailer.error(f"{dataset} doesn't have operational state")
        else:
            operations[operation][state] += 1
            if state in ("FAILED", "WARNING"):
                detailer.error(f"{operation} {state} for {dataset}: {message!r}")
                if operation == "INDEX":
                    match = index_pattern.match(message)
                    if match:
                        try:
                            code = int(match.group(1))
                            message = match.group(2)
                            index_errors[code] += 1
                            if code not in index_messages:
                                index_messages[code] = message
                        except Exception as e:
                            detailer.error(
                                f"{dataset} unexpected 'INDEX' error {message}: {str(e)!r}"
                            )
    click.echo("Operational states:")
    for name, states in operations.items():
        click.echo(f"  {name} states:")
        for state, count in states.items():
            click.echo(f"    {state:>8s} {count:>8,d}")
            if name == "INDEX" and state == "FAILED":
                for code, count in index_errors.items():
                    click.echo(
                        f"           CODE {code:2d}: {count:>6,d}  {index_messages[code]}"
                    )
    if ops_anomalies:
        click.echo(f"  {ops_anomalies} datasets are missing operational state")


@click.command(name="pbench-report-generator")
@pass_cli_context
@click.option("--all", "-a", default=False, is_flag=True, help="Display full report")
@click.option(
    "--archive", "-A", default=False, is_flag=True, help="Display archive statistics"
)
@click.option(
    "--audit", "-L", default=False, is_flag=True, help="Display audit log statistics"
)
@click.option(
    "--backup", "-b", default=False, is_flag=True, help="Display backup statistics"
)
@click.option(
    "--cache", "-c", default=False, is_flag=True, help="Display cache statistics"
)
@click.option(
    "--detail",
    "-d",
    default=False,
    is_flag=True,
    help="Provide extra diagnostic information",
)
@click.option(
    "--errors",
    "-e",
    default=False,
    is_flag=True,
    help="Show individual file errors",
)
@click.option(
    "--progress", "-p", type=float, default=0.0, help="Show periodic progress messages"
)
@click.option("--sql", "-s", default=False, is_flag=True, help="Display SQL statistics")
@click.option(
    "--states", "-S", default=False, is_flag=True, help="Display operational states"
)
@click.option(
    "--statistics",
    type=click.Choice(["creation", "upload"], case_sensitive=False),
    help="Show upload statistics",
)
@click.option(
    "--verify", "-v", default=False, is_flag=True, help="Display intermediate messages"
)
@click.option("--width", type=int, default=80, help="Set output width")
@common_options
def report(context: object, **kwargs):
    """
    Report statistics and problems in the SQL and on-disk representation of
    Pbench datasets.
    \f

    Args:
        context: click context
        kwargs: click options
    """
    logger = None

    global detailer, verifier, watcher
    detailer = Detail(kwargs.get("detail"), kwargs.get("errors"))
    verifier = Verify(kwargs.get("verify"))
    watcher = Watch(kwargs.get("progress"))
    rv = 0

    try:
        config = config_setup(context)
        logger = get_pbench_logger("pbench-report-generator", config)
        cache_m = CacheManager(config, logger)
        if any((kwargs.get("all"), kwargs.get("archive"), kwargs.get("backup"))):
            verifier.status("starting discovery")
            watcher.update("discovering archive tree")
            cache_m.full_discovery(search=False)
            watcher.update("processing reports")
            verifier.status("finished discovery")
            if kwargs.get("all") or kwargs.get("archive"):
                report_archive(cache_m)
            if kwargs.get("all") or kwargs.get("backup"):
                report_backup(cache_m)
        if kwargs.get("all") or kwargs.get("cache"):
            report_cache(cache_m)
        stats = kwargs.get("statistics")
        if stats:
            if stats == "creation":
                report_creation(kwargs)
            elif stats == "upload":
                report_uploads(kwargs)
            else:
                click.echo(f"Unexpected statistics option {stats}", err=True)
                rv = 1
        if kwargs.get("all") or kwargs.get("audit"):
            report_audit()
        if kwargs.get("all") or kwargs.get("sql"):
            report_sql()
        if kwargs.get("all") or kwargs.get("states"):
            report_states()
        watcher.update("done")
    except Exception as exc:
        if logger:
            logger.exception("An error occurred discovering the file tree: {}", exc)
        if kwargs.get("verify"):
            raise
        click.secho(exc, err=True, bg="red")
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
