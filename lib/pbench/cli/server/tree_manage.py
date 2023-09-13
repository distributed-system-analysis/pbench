from datetime import datetime, timedelta, timezone
import errno
from logging import Logger

import click

from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup
from pbench.cli.server.options import common_options
from pbench.common.logger import get_pbench_logger
from pbench.server import BadConfig, OperationCode
from pbench.server.cache_manager import CacheManager, LockRef
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType

# Length of time in hours to retain unreferenced cached results data.
# TODO: this could become a configurable setting?
CACHE_LIFETIME = 4.0


def reclaim_cache(tree: CacheManager, logger: Logger, lifetime: float = CACHE_LIFETIME):
    """Reclaim unused caches

    Args:
        tree: the cache manager instance
        lifetime: number of hours to retain unused cache data
        logger: a Logger object
    """
    window = datetime.now(timezone.utc) - timedelta(hours=lifetime)
    total_count = 0
    has_cache = 0
    reclaimed = 0
    reclaim_failed = 0
    for tarball in tree.datasets.values():
        total_count += 1
        if tarball.unpacked:
            has_cache += 1
            date = datetime.fromtimestamp(
                tarball.last_ref.stat().st_mtime, timezone.utc
            )
            if date >= window:
                continue
            error = None
            audit = None
            logger.info(
                "RECLAIM {}: last_ref {:%Y-%m-%d %H:%M:%S} is older than {:%Y-%m-%d %H:%M:%S}",
                tarball.name,
                date,
                window,
            )
            try:
                with LockRef(tarball.lock, exclusive=True, wait=False):
                    try:
                        audit = Audit.create(
                            name="reclaim",
                            operation=OperationCode.DELETE,
                            status=AuditStatus.BEGIN,
                            user_name=Audit.BACKGROUND_USER,
                            object_type=AuditType.DATASET,
                            object_id=tarball.resource_id,
                            object_name=tarball.name,
                        )
                    except Exception as e:
                        logger.warn(
                            "Unable to audit cache reclaim for {}: '{}'",
                            tarball.name,
                            e,
                        )
                    try:
                        tarball.cache_delete()
                        reclaimed += 1
                    except Exception as e:
                        error = e
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EACCES):
                    logger.info(
                        "RECLAIM {}: skipping because cache is locked",
                        tarball.name,
                    )
                    # If the cache is locked, regardless of age, then
                    # the last_ref timestamp is about to be updated,
                    # and we skip the dataset this time around.
                    continue
                error = e
            except Exception as e:
                error = e
            attributes = {"last_ref": f"{date:%Y-%m-%d %H:%M:%S}"}
            if error:
                reclaim_failed += 1
                logger.error("RECLAIM {} failed with '{}'", tarball.name, error)
                attributes["error"] = str(error)
            if audit:
                Audit.create(
                    root=audit,
                    status=AuditStatus.FAILURE if error else AuditStatus.SUCCESS,
                    attributes=attributes,
                )
    logger.info(
        "RECLAIM summary: {} datasets, {} had cache: {} reclaimed and {} errors",
        total_count,
        has_cache,
        reclaimed,
        reclaim_failed,
    )


def print_tree(tree: CacheManager):
    """Print basic information about the cache

    Args:
        tree: a cache instance
    """
    print(f"Tree anchored at {tree.archive_root}\n")

    if len(tree.datasets) == 0 and len(tree.controllers) == 0:
        print("Pbench file tree is empty")
        return

    print("Tarballs:")
    for tarball in tree.datasets.values():
        print(f"  {tarball.name}")
        if tarball.unpacked:
            date = datetime.fromtimestamp(
                tarball.last_ref.stat().st_mtime, timezone.utc
            )
            print(f"    Inventory is cached, last referenced {date:%Y-%m-%d %H:%M:%S}")

    print("\nControllers:")
    for controller in tree.controllers.values():
        print(f"  Controller {controller.name}:")
        for tarball in controller.tarballs.values():
            print(f"    Tarball {tarball.name}")


@click.command(name="pbench-tree-manager")
@pass_cli_context
@click.option(
    "--display", default=False, is_flag=True, help="Display the full tree on completion"
)
@click.option(
    "--reclaim",
    show_default=True,
    is_flag=False,
    flag_value=CACHE_LIFETIME,
    type=click.FLOAT,
    help="Reclaim cached data older than <n> hours",
)
@common_options
def tree_manage(context: object, display: bool, reclaim: float):
    """
    Discover, display, and manipulate the on-disk representation of controllers
    and datasets.

    This primarily exposes the CacheManager object hierarchy, and provides a
    hierarchical display of controllers and datasets. This also supports
    reclaiming cached dataset files that haven't been referenced recently.
    \f

    Args:
        context: Click context (contains shared `--config` value)
        display: Print a simplified representation of the hierarchy
        lifetime: Number of hours to retain unused cache before reclaim
        reclaim: Reclaim stale cached data
    """
    try:
        config = config_setup(context)
        logger = get_pbench_logger("cachemanager", config)
        cache_m = CacheManager(config, logger)
        cache_m.full_discovery()
        if display:
            print_tree(cache_m)
        if reclaim:
            reclaim_cache(cache_m, logger, reclaim)
        rv = 0
    except Exception as exc:
        logger.exception("An error occurred discovering the file tree: {}", exc)
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
