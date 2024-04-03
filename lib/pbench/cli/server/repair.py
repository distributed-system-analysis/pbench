from collections import defaultdict
import copy
import datetime
from operator import and_
from pathlib import Path
from typing import Any, Optional

import click
from sqlalchemy import cast, column, or_, String, Subquery
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import func

from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup, Detail, Verify, Watch
from pbench.cli.server.options import common_options
from pbench.common.logger import get_pbench_logger
from pbench.server import BadConfig, cache_manager
from pbench.server.database.database import Database
from pbench.server.database.models.audit import Audit
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.server_settings import get_retention_days
from pbench.server.utils import UtcTimeHelper

detailer: Optional[Detail] = None
watcher: Optional[Watch] = None
verifier: Optional[Verify] = None


LIMIT = cache_manager.MAX_ERROR


def repair_audit(kwargs):
    """Repair certain audit record problems.

    1. truncate extremely long audit event "attributes"

    Args:
        kwargs: the command options.
    """

    rows = (
        Database.db_session.query(Audit)
        .filter(func.length(cast(Audit.attributes, String)) >= LIMIT)
        .order_by(Audit.timestamp)
        .execution_options(stream_results=True)
        .yield_per(2000)
    )
    count = 0
    attributes_errors = 0
    updated = 0
    commit_error = None
    for audit in rows:
        count += 1
        name = f"{audit.id}:{audit.status.name} {audit.name} {audit.object_name}"
        # Deep copy works around a limitation in SQLAlchemy JSON proxy handling
        a: dict[str, Any] = copy.deepcopy(audit.attributes)
        if type(a) is not dict:
            detailer.error(f"{name} attributes is type {type(a).__name__}")
            attributes_errors += 1
            continue
        didit = False
        for key, value in a.items():
            if type(value) is str and len(value) > LIMIT:
                p = f"[TRUNC({len(value)})]"
                a[key] = (p + value)[:LIMIT]
                detailer.message(f"{name} [{key}] truncated ({len(value)}) to {LIMIT}")
                didit = True
        if didit:
            audit.attributes = a
            updated += 1
    if updated:
        try:
            Database.db_session.commit()
        except Exception as e:
            commit_error = str(e)
    click.echo(f"{count} audit records triggered field truncation")
    click.echo(
        f"{updated} records were truncated, {count-updated} had no eligible fields"
    )
    if attributes_errors:
        click.echo(f"{attributes_errors} had format errors in attributes")
    if commit_error:
        click.echo(f"SQL error, changes were not made: {commit_error!r}")


def find_tarball(resource_id: str, kwargs) -> Optional[Path]:
    """Find a tarball in the ARCHIVE tree

    This is a "brute force" helper to repair a missing server.tarball-path
    metadata. We can't use the cache manager find_dataset(), which relies
    on server.tarball-path; so instead we do a search for the MD5 value.

    Args:
        resource_id: the dataset resource ID (MD5)
        kwargs: CLI options

    Returns:
        tarball path if found, or None
    """

    def get_md5(file: Path) -> Optional[str]:
        """Locate and read a tarball's associated MD5 hash"""
        md5 = file.with_suffix(".xz.md5")
        if md5.is_file():
            return md5.read_text().split(" ", maxsplit=1)[0]
        else:
            detailer.error(f"Missing MD5 {md5}")
            return None

    # We use the cache manager as a standard way to get the ARCHIVE root
    tree = cache_manager.CacheManager(kwargs["_config"], kwargs["_logger"])
    for controller in tree.archive_root.iterdir():
        watcher.update(f"searching {controller} for {resource_id}")
        if controller.is_dir():
            isolator = controller / resource_id
            if isolator.is_dir():
                tars = list(isolator.glob("*.tar.xz"))
                if len(tars) > 1:
                    detailer.error(
                        f"Isolator directory {isolator} contains multiple tarballs: {[str(t) for t in tars]}"
                    )
                for tar in tars:
                    if get_md5(tar) == resource_id:
                        verifier.status(f"Found {tar} for ID {resource_id}", 2)
                        return tar
                detailer.error(
                    f"Isolator directory {isolator} doesn't contain a tarball for {resource_id}"
                )
                return None
            else:
                for tar in controller.glob("**/*.tar.xz"):
                    if get_md5(tar) == resource_id:
                        verifier.status(f"Found {tar} for ID {resource_id}", 2)
                        return tar
    return None


def repair_metadata(kwargs):
    """Repair certain critical metadata errors

    1. Missing server.tarball-path
    2. Missing dataset.metalog
    3. Missing server.benchmark

    Args:
        kwargs: the command options
    """

    # In order to filter on "derived" values like the JSON path extraction,
    # we need to use a nested SELECT -- PostgreSQL doesn't allow using an
    # "as" label in the WHERE clause, but labeling the nested SELECT columns
    # gets around that limitation. We also do two OUTER JOINs in order to
    # filter only for datasets where one of the three things we know how to
    # repair is missing.
    mlog = aliased(Metadata, name="metalog")
    meta: Subquery = (
        Database.db_session.query(
            Metadata.dataset_ref,
            Metadata.value["tarball-path"].label("path"),
            Metadata.value["benchmark"].label("benchmark"),
            Metadata.value["deletion"].label("expiration"),
        )
        .where(Metadata.key == "server")
        .subquery()
    )
    query = (
        Database.db_session.query(
            Dataset, meta.c.path, meta.c.benchmark, meta.c.expiration, mlog
        )
        .outerjoin(meta, Dataset.id == meta.c.dataset_ref)
        .outerjoin(
            mlog, and_(Dataset.id == mlog.dataset_ref, mlog.key == Metadata.METALOG)
        )
        .filter(
            or_(
                meta.c.path.is_(None),
                meta.c.benchmark.is_(None),
                meta.c.expiration.is_(None),
                column("metalog").is_(None),
            )
        )
        .execution_options(stream_results=True)
    )

    path_repairs = 0
    expiration_repairs = 0
    benchmark_repairs = 0
    metalog_repairs = 0
    path_repairs_failed = 0
    expiration_repairs_failed = 0
    metalog_repairs_failed = 0
    rows = query.yield_per(2000)

    # We have to finish reading before we can write metadata, or we'll confuse
    # SQLAlchemy's cursor logic. So build a defer queue for metadata values to
    # set. (Another alternative would be to list-ify the query: it's unclear
    # which would scale better.)
    defer = []
    for dataset, path, benchmark, expiration, metadata in rows:
        fix = {"dataset": dataset, "metadata": defaultdict()}
        if not path:
            path_repairs += 1
            path = find_tarball(dataset.resource_id, kwargs)
            if path:
                detailer.message(
                    f"{dataset.name} has no {Metadata.TARBALL_PATH}: setting {path}"
                )
                fix["metadata"][Metadata.TARBALL_PATH] = str(path)
            else:
                path_repairs_failed += 1
                detailer.error(f"{dataset.name} doesn't seem to have a tarball")
        if not metadata or not metadata.value:
            metalog_repairs += 1
            which = "metadata.log"
            try:
                metalog = cache_manager.Tarball._get_metadata(path)
            except Exception:
                which = "default"
                metalog = {
                    "pbench": {
                        "name": dataset.name,
                        "script": Metadata.SERVER_BENCHMARK_UNKNOWN,
                    }
                }
                fix["metadata"][Metadata.SERVER_ARCHIVE] = True
            detailer.message(
                f"{dataset.name} has no {Metadata.METALOG}: setting from {which}"
            )
            fix["metalog"] = metalog
        else:
            metalog = metadata.value

        if not expiration:
            expiration_repairs += 1
            try:
                retention_days = get_retention_days(kwargs.get("_config"))
                retention = datetime.timedelta(days=retention_days)
                deletion = UtcTimeHelper(dataset.uploaded + retention).to_iso_string()
                fix["metadata"][Metadata.SERVER_DELETION] = deletion
                detailer.message(
                    f"{dataset.name} {Metadata.SERVER_DELETION} "
                    f"set ({retention_days} days) to {deletion}"
                )
            except Exception as e:
                detailer.error(
                    f"unable to calculate {dataset.name} expiration: {str(e)!r}"
                )
                expiration_repairs_failed += 1

        if not benchmark:
            benchmark_repairs += 1
            script = metalog.get("pbench", {}).get(
                "script", Metadata.SERVER_BENCHMARK_UNKNOWN
            )
            detailer.message(
                f"{dataset.name} has no {Metadata.SERVER_BENCHMARK}: setting {script!r}"
            )
            fix["metadata"][Metadata.SERVER_BENCHMARK] = script
        defer.append(fix)
    for each in defer:
        dataset = each["dataset"]
        metalog = each.get("metalog")
        if metalog:
            try:
                Metadata.create(dataset=dataset, key=Metadata.METALOG, value=metalog)
            except Exception as e:
                metalog_repairs_failed += 1
                detailer.error(f"Unable to create {dataset.name} metalog: {str(e)!r}")
        for key, value in each.get("metadata", {}).items():
            Metadata.setvalue(dataset, key, value)

    click.echo(
        f"{path_repairs} {Metadata.TARBALL_PATH} repairs, "
        f"{path_repairs_failed} failures"
    )
    click.echo(
        f"{expiration_repairs} {Metadata.SERVER_DELETION} repairs, "
        f"{expiration_repairs_failed} failures"
    )
    click.echo(
        f"{metalog_repairs} dataset.metalog repairs, "
        f"{metalog_repairs_failed} failures"
    )
    click.echo(f"{benchmark_repairs} {Metadata.SERVER_BENCHMARK} repairs")


@click.command(name="pbench-repair")
@pass_cli_context
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
@click.option(
    "--verify", "-v", default=False, count=True, help="Display intermediate messages"
)
@common_options
def repair(context: object, **kwargs):
    """Repair consistency problems in the Pbench Server data
    \f

    Args:
        context: click context
        kwargs: click options
    """
    global detailer, verifier, watcher
    detailer = Detail(kwargs.get("detail"), kwargs.get("errors"))
    verifier = Verify(kwargs.get("verify"))
    watcher = Watch(kwargs.get("progress"))

    try:
        config = config_setup(context)
        kwargs["_logger"] = get_pbench_logger("pbench-repair", config)
        kwargs["_config"] = config
        verifier.status("Repairing audit")
        watcher.update("repairing audit")
        repair_audit(kwargs)
        verifier.status("Repairing metadata")
        watcher.update("repairing metadata")
        repair_metadata(kwargs)
        rv = 0
    except Exception as exc:
        if verifier.verify:
            raise
        click.secho(exc, err=True, bg="red")
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
