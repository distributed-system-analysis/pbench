from collections import defaultdict
import datetime
import re
from threading import Thread
import time
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

# An arbitrary really big number
GINORMOUS = 2**64


class Detail:
    """Encapsulate generation of additional diagnostics"""

    def __init__(self, detail: bool = False, errors: bool = False):
        """Initialize the object.

        Args:
            detail: True if detailed messages should be generated
            errors: True if individual file errors should be reported
        """
        self.detail = detail
        self.errors = errors

    def __bool__(self) -> bool:
        """Report whether detailed messages are enabled

        Returns:
            True if details are enabled
        """
        return self.detail

    def error(self, message: str):
        """Write a message if details are enabled.

        Args:
            message: Detail string
        """
        if self.errors:
            click.secho(f"|| {message}", fg="red")

    def message(self, message: str):
        """Write a message if details are enabled.

        Args:
            message: Detail string
        """
        if self.detail:
            click.echo(f"|| {message}")


class Verify:
    """Encapsulate -v status messages."""

    def __init__(self, verify: bool):
        """Initialize the object.

        Args:
            verify: True to write status messages.
        """
        self.verify = verify

    def __bool__(self) -> bool:
        """Report whether verification is enabled.

        Returns:
            True if verification is enabled.
        """
        return self.verify

    def status(self, message: str):
        """Write a message if verification is enabled.

        Args:
            message: status string
        """
        if self.verify:
            ts = datetime.datetime.now().astimezone()
            click.secho(f"({ts:%H:%M:%S}) {message}", fg="green")


class Watch:
    """Encapsulate a periodic status update.

    The active message can be updated at will; a background thread will
    periodically print the most recent status.
    """

    def __init__(self, interval: float):
        """Initialize the object.

        Args:
            interval: interval in seconds for status updates
        """
        self.start = time.time()
        self.interval = interval
        self.status = "starting"
        if interval:
            self.thread = Thread(target=self.watcher)
            self.thread.setDaemon(True)
            self.thread.start()

    def update(self, status: str):
        """Update status if appropriate.

        Update the message to be printed at the next interval, if progress
        reporting is enabled.

        Args:
            status: status string
        """
        self.status = status

    def watcher(self):
        """A worker thread to periodically write status messages."""

        while True:
            time.sleep(self.interval)
            now = time.time()
            delta = int(now - self.start)
            hours, remainder = divmod(delta, 3600)
            minutes, seconds = divmod(remainder, 60)
            click.secho(
                f"[{hours:02d}:{minutes:02d}:{seconds:02d}] {self.status}", fg="cyan"
            )


detailer: Optional[Detail] = None
watcher: Optional[Watch] = None
verifier: Optional[Verify] = None


def report_archive(tree: CacheManager):
    """Report archive statistics.

    Args:
        tree: a cache instance
    """

    watcher.update("inspecting archive")
    tarball_count = len(tree.datasets)
    tarball_size = 0
    smallest_tarball = GINORMOUS
    smallest_tarball_name = None
    biggest_tarball = 0
    biggest_tarball_name = None

    for tarball in tree.datasets.values():
        watcher.update(f"({tarball_count}) archive {tarball.name}")
        size = tarball.tarball_path.stat().st_size
        tarball_size += size
        if size < smallest_tarball:
            smallest_tarball = size
            smallest_tarball_name = tarball.name
        if size > biggest_tarball:
            biggest_tarball = size
            biggest_tarball_name = tarball.name
    click.echo("Archive report:")
    click.echo(
        f"  {tarball_count:,d} tarballs consuming {humanize.naturalsize(tarball_size)}"
    )
    click.echo(
        f"  The smallest tarball is {humanize.naturalsize(smallest_tarball)}, "
        f"{smallest_tarball_name}"
    )
    click.echo(
        f"  The biggest tarball is {humanize.naturalsize(biggest_tarball)}, "
        f"{biggest_tarball_name}"
    )


def report_backup(tree: CacheManager):
    """Report tarball backup statistics.

    Args:
        tree: a cache instance
    """

    watcher.update("inspecting backups")
    backup_count = 0
    backup_size = 0
    for tarball in tree.backup_root.glob("**/*.tar.xz"):
        watcher.update(f"({backup_count}) backup {Dataset.stem(tarball)}")
        backup_count += 1
        backup_size += tarball.stat().st_size

    click.echo("Backup report:")
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
    bad_size = 0
    oldest_cache = time.time() * 2.0  # moderately distant future
    oldest_cache_name = None
    newest_cache = 0.0  # wayback machine
    newest_cache_name = None
    smallest_cache = GINORMOUS
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
                detailer.error(f"{tarball.name} last ref access: {str(e)!r}")
                last_ref_errors += 1
            else:
                if referenced < oldest_cache:
                    oldest_cache = referenced
                    oldest_cache_name = tarball.name
                if referenced > newest_cache:
                    newest_cache = referenced
                    newest_cache_name = tarball.name
            cached_count += 1
            size = Metadata.getvalue(tarball.dataset, Metadata.SERVER_UNPACKED)
            if not size:
                detailer.error(f"{tarball.name} has no unpacked size")
                lacks_size += 1
            elif not isinstance(size, int):
                detailer.error(
                    f"{tarball.name} has non-integer unpacked size "
                    f"{size!r} ({type(size)})"
                )
                bad_size += 1
            else:
                if size < smallest_cache:
                    smallest_cache = size
                    smallest_cache_name = tarball.name
                if size > biggest_cache:
                    biggest_cache = size
                    biggest_cache_name = tarball.name
                cached_size += size
    oldest = datetime.datetime.fromtimestamp(oldest_cache, datetime.timezone.utc)
    newest = datetime.datetime.fromtimestamp(newest_cache, datetime.timezone.utc)
    click.echo("Cache report:")
    click.echo(
        f"  {cached_count:,d} datasets consuming "
        f"{humanize.naturalsize(cached_size)}"
    )
    click.echo(
        f"  {lacks_size:,d} datasets have never been unpacked, "
        f"{last_ref_errors:,d} are missing reference timestamps, "
        f"{bad_size:,d} have bad size metadata"
    )
    click.echo(
        f"  The smallest cache is {humanize.naturalsize(smallest_cache)}, "
        f"{smallest_cache_name}"
    )
    click.echo(
        f"  The biggest cache is {humanize.naturalsize(biggest_cache)}, "
        f"{biggest_cache_name}"
    )
    click.echo(
        "  The least recently used cache was referenced "
        f"{humanize.naturaldate(oldest)}, {oldest_cache_name}"
    )
    click.echo(
        "  The most recently used cache was referenced "
        f"{humanize.naturaldate(newest)}, {newest_cache_name}"
    )


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
    ).yield_per(500):
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
        )
    )
    for dataset, operation, state, message in rows:
        watcher.update(f"inspecting {dataset}:{operation}")
        if operation is None:
            ops_anomalies += 1
            detailer.error(f"{dataset} doesn't have operational state")
        else:
            operations[operation][state] += 1
            if state == "FAILED":
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
    "--verify", "-v", default=False, is_flag=True, help="Display intermediate messages"
)
@common_options
def report(
    context: object,
    all: bool,
    archive: bool,
    backup: bool,
    cache: bool,
    detail: bool,
    errors: bool,
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
        errors: show individual file errors
        sql: report SQL statistics
        states: report operational states
        verify: Report internal status
    """
    logger = None

    global detailer, verifier, watcher
    detailer = Detail(detail, errors)
    verifier = Verify(verify)
    watcher = Watch(progress)

    try:
        config = config_setup(context)
        logger = get_pbench_logger("pbench-report-generator", config)
        if any((all, archive, backup, cache)):
            cache_m = CacheManager(config, logger)
            verifier.status("starting discovery")
            watcher.update("discovering cache")
            cache_m.full_discovery()
            watcher.update("processing reports")
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
        watcher.update("done")

        rv = 0
    except Exception as exc:
        if logger:
            logger.exception("An error occurred discovering the file tree: {}", exc)
        if verify:
            raise
        click.secho(exc, err=True, bg="red")
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
