from collections import defaultdict
import datetime
from typing import Optional

import click
import humanize
from sqlalchemy import inspect, select, text

from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup
from pbench.cli.server.options import common_options
from pbench.client.types import Dataset
from pbench.common.logger import get_pbench_logger
from pbench.server import BadConfig
from pbench.server.cache_manager import CacheManager
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Metadata
from pbench.server.database.models.index_map import IndexMap


class Detail:
    """Encapsulate generation of additional diagnostics"""

    def __init__(self, detail: bool):
        self.detail = detail

    def __bool__(self) -> bool:
        return self.detail

    def write(self, message: str):
        if self.detail:
            click.echo(f"|| {message}")


class Verify:
    """Encapsulate -v status messages."""

    def __init__(self, verify: bool):
        self.verify = verify

    def __bool__(self) -> bool:
        return self.verify

    def status(self, message: str):
        if self.verify:
            ts = datetime.datetime.now()
            click.echo(f"({ts:%H:%M:%S}) {message}")


class Watch:
    """Encapsulate a periodic status check.

    Discovery (especially for cache and backup) can take a long time, so we
    centralize a periodic update notice mechanism.
    """

    def __init__(self, interval: float):
        self.interval = datetime.timedelta(seconds=interval) if interval else None
        self.start = datetime.datetime.now()
        self.last = self.start

    def update(self, status: str):
        now = datetime.datetime.now()
        if self.interval and now > self.last + self.interval:
            self.last = now
            delta = now - self.start
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            click.echo(f"[{hours:02d}:{minutes:02d}:{seconds:02d}] {status}")


detailer: Optional[Detail] = None
watcher: Optional[Watch] = None
verifier: Optional[Verify] = None


def report_archive(tree: CacheManager):
    """Report archive statistics.

    Args:
        tree: a cache instance
    """

    tarball_count = len(tree.datasets)
    tarball_size = 0
    smallest_tarball = 0
    smallest_tarball_name = None
    biggest_tarball = 0
    biggest_tarball_name = None

    for tarball in tree.datasets.values():
        watcher.update(f"({tarball_count}) archive {tarball.name}")
        size = tarball.tarball_path.stat().st_size
        tarball_size += size
        if not smallest_tarball or size < smallest_tarball:
            smallest_tarball = size
            smallest_tarball_name = tarball.name
        if not biggest_tarball or size > biggest_tarball:
            biggest_tarball = size
            biggest_tarball_name = tarball.name
    click.echo("Archive report:")
    click.echo(
        f"  {tarball_count:d} tarballs consuming {humanize.naturalsize(tarball_size)}"
    )
    click.echo(
        f"  The smallest tarball, {smallest_tarball_name}, is "
        f"{humanize.naturalsize(smallest_tarball)}"
    )
    click.echo(
        f"  The biggest tarball, {biggest_tarball_name}, is "
        f"{humanize.naturalsize(biggest_tarball)}"
    )


def report_backup(tree: CacheManager):
    """Report tarball backup statistics.

    Args:
        tree: a cache instance
    """

    backup_count = 0
    backup_size = 0
    for tarball in tree.backup_root.glob("**/*.tar.xz"):
        watcher.update(f"({backup_count}) backup {Dataset.stem(tarball)}")
        backup_count += 1
        backup_size += tarball.stat().st_size

    click.echo("Backup report:")
    click.echo(
        f"  {backup_count} tarballs are backed up, consuming "
        f"{humanize.naturalsize(backup_size)}"
    )


def report_cache(tree: CacheManager):
    """Report cache statistics.

    Args:
        tree: a cache instance
    """

    cached_count = 0
    cached_size = 0
    lacks_size = 0
    bad_size = 0
    oldest_cache = None
    oldest_cache_name = None
    newest_cache = None
    newest_cache_name = None
    smallest_cache = 0
    smallest_cache_name = None
    biggest_cache = 0
    biggest_cache_name = None
    last_ref_errors = 0

    for tarball in tree.datasets.values():
        watcher.update(f"({cached_count}) cache {tarball.name}")
        if tarball.unpacked:
            try:
                referenced = tarball.last_ref.stat().st_mtime
            except Exception as e:
                detailer.write(f"{tarball.name} last ref access: {str(e)!r}")
                last_ref_errors += 1
            else:
                if not oldest_cache or referenced < oldest_cache:
                    oldest_cache = referenced
                    oldest_cache_name = tarball.name
                if not newest_cache or referenced > newest_cache:
                    newest_cache = referenced
                    newest_cache_name = tarball.name
            cached_count += 1
            size = Metadata.getvalue(tarball.dataset, Metadata.SERVER_UNPACKED)
            if not size:
                detailer.write(f"{tarball.name} has no unpacked size")
                lacks_size += 1
            elif not isinstance(size, int):
                detailer.write(
                    f"{tarball.name} has non-integer unpacked size "
                    f"{size!r} ({type(size)})"
                )
                bad_size += 1
            else:
                if not smallest_cache or size < smallest_cache:
                    smallest_cache = size
                    smallest_cache_name = tarball.name
                if not biggest_cache or size > biggest_cache:
                    biggest_cache = size
                    biggest_cache_name = tarball.name
                cached_size += size
    oldest = datetime.datetime.fromtimestamp(oldest_cache, datetime.timezone.utc)
    newest = datetime.datetime.fromtimestamp(newest_cache, datetime.timezone.utc)
    click.echo("Cache report:")
    click.echo(
        f"  {cached_count} datasets are cached, consuming "
        f"{humanize.naturalsize(cached_size)}"
    )
    click.echo(
        f"  {lacks_size} datasets have never been unpacked, "
        f"{last_ref_errors} are missing reference timestamps, "
        f"{bad_size} have bad size metadata"
    )
    click.echo(
        f"  The smallest cache, {smallest_cache_name}, is "
        f"{humanize.naturalsize(smallest_cache)}"
    )
    click.echo(
        f"  The biggest cache, {biggest_cache_name}, is "
        f"{humanize.naturalsize(biggest_cache)}"
    )
    click.echo(
        f"  The least recently used cache, {oldest_cache_name}, was "
        f"referenced {humanize.naturaldate(oldest)}"
    )
    click.echo(
        f"  The most recently used cache, {newest_cache_name}, was "
        f"referenced {humanize.naturaldate(newest)}"
    )


def report_sql():
    """Report the SQL table storage statistics"""
    click.echo("SQL storage report:")
    click.echo("  Table                Rows       Storage")
    click.echo("  -------------------- ---------- ----------")
    for t in inspect(Database.db_session.get_bind()).get_table_names():
        rows = list(
            Database.db_session.execute(statement=text(f"SELECT COUNT(*) FROM {t}"))
        )[0][0]
        size = list(
            Database.db_session.execute(
                statement=text("SELECT pg_total_relation_size(:table)"),
                params={"table": t},
            )
        )[0][0]
        click.echo(f"  {t:20} {rows:>10} {humanize.naturalsize(size):>10}")

    if not detailer:
        return

    query = select(IndexMap.root, IndexMap.index)
    idxes = Database.db_session.execute(query).all()
    record_count = 0
    roots = set()
    indices = set()
    root_size = 0
    index_size = 0
    for idx in idxes:
        record_count += 1
        roots.add(idx[0])
        indices.add(idx[1])
        root_size += len(idx[0])
        index_size += len(idx[1])
    unique_root_size = 0
    unique_index_size = 0
    for r in roots:
        unique_root_size += len(r)
    for i in indices:
        unique_index_size += len(i)

    detailer.write(
        f"{record_count} indexmap records found with {len(indices)} indices "
        f"and {len(roots)} roots:"
    )
    detailer.write(
        f" {humanize.naturalsize(index_size)} for index names, "
        f"{humanize.naturalsize(root_size)} for root names"
    )
    detailer.write(
        f" deduped: {humanize.naturalsize(unique_index_size)} for index "
        f"names, {humanize.naturalsize(unique_root_size)} for root names"
    )


def report_states():
    """Report tarball operational states."""

    operations = defaultdict(lambda: defaultdict(int))
    rows = Database.db_session.execute(
        statement=text(
            "SELECT d.name, o.name, o.state, o.message FROM datasets AS d LEFT OUTER JOIN "
            "dataset_operations AS o ON o.dataset_ref = d.id"
        )
    )
    for row in rows:
        operations[row[1]][row[2]] += 1
        if row[2] == "FAILED":
            detailer.write(f"{row[1]} {row[2]} {row[0]} {row[3]!r}")
    click.echo("Operational states:")
    for name, states in operations.items():
        click.echo(f"  {name} states:")
        for state, count in states.items():
            click.echo(f"    {state:>8s} {count:>8d}")


@click.command(name="pbench-report-generator")
@pass_cli_context
@click.option("--all", default=False, is_flag=True, help="Display full report")
@click.option(
    "--archive", default=False, is_flag=True, help="Display archive statistics"
)
@click.option("--backup", default=False, is_flag=True, help="Display backup statistics")
@click.option("--cache", default=False, is_flag=True, help="Display cache statistics")
@click.option(
    "--detail", default=False, is_flag=True, help="Provide extra diagnostic information"
)
@click.option(
    "--progress", type=float, default=0.0, help="Show periodic progress messages"
)
@click.option("--sql", default=False, is_flag=True, help="Display SQL statistics")
@click.option(
    "--states", default=False, is_flag=True, help="Display operational states"
)
@click.option(
    "--verify", default=False, is_flag=True, help="Display intermediate messages"
)
@common_options
def report(
    context: object,
    all: bool,
    archive: bool,
    backup: bool,
    cache: bool,
    detail: bool,
    progress: float,
    sql: bool,
    states: bool,
    verify: bool,
):
    """
    Report statistics and problems in the SQL and on-disk representation of
    Pbench datasets.
    \f

    Args:
        context: click context
        all: report all statistics
        archive: report archive statistics
        backup: report backup statistics
        cache: report cache statistics
        detail: provide additional per-file diagnostics
        sql: report SQL statistics
        states: report operational states
        verify: Report internal status
    """
    logger = None

    global detailer, verifier, watcher
    detailer = Detail(detail)
    verifier = Verify(verify)
    watcher = Watch(progress)

    try:
        config = config_setup(context)
        logger = get_pbench_logger("report-generator", config)
        if any((all, archive, backup, cache)):
            cache_m = CacheManager(config, logger)
            verifier.status("starting discovery")
            cache_m.full_discovery()
            verifier.status("finished discovery")
            if all or archive:
                report_archive(cache_m)
            if all or backup:
                report_backup(cache_m)
            if all or cache:
                report_cache(cache_m)
        if all or sql:
            report_sql()
        if all or states:
            report_states()

        rv = 0
    except Exception as exc:
        if logger:
            logger.exception("An error occurred discovering the file tree: {}", exc)
        if verify:
            raise
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
