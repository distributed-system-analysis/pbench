import datetime
from typing import Optional

import click
import humanfriendly

from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup, Detail, Verify, Watch
from pbench.cli.server.options import common_options
from pbench.common.logger import get_pbench_logger
from pbench.server import BadConfig
from pbench.server.cache_manager import CacheManager

detailer: Optional[Detail] = None
watcher: Optional[Watch] = None
verifier: Optional[Verify] = None


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
            date = datetime.datetime.fromtimestamp(
                tarball.last_ref.stat().st_mtime, datetime.timezone.utc
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
    "--detail",
    "-d",
    default=False,
    is_flag=True,
    help="Provide extra diagnostic information",
)
@click.option(
    "--display", default=False, is_flag=True, help="Display the full tree on completion"
)
@click.option(
    "--progress", "-p", type=float, default=0.0, help="Show periodic progress messages"
)
@click.option(
    "--reclaim-percent",
    show_default=True,
    is_flag=False,
    flag_value=20.0,
    type=click.FLOAT,
    help="Reclaim cached data to maintain a target % free space",
)
@click.option(
    "--reclaim-size",
    is_flag=False,
    help="Reclaim cached data to maintain specified free space",
)
@click.option(
    "--search",
    is_flag=True,
    help="Do an exhaustive search of ARCHIVE tree rather than using SQL",
)
@click.option(
    "--verify", "-v", default=False, is_flag=True, help="Display intermediate messages"
)
@common_options
def tree_manage(
    context: object,
    detail: bool,
    display: bool,
    progress: float,
    reclaim_percent: float,
    reclaim_size: str,
    search: bool,
    verify: bool,
):
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
        reclaim-percent: Reclaim cached data to free specified % on drive
        reclaim-size: Reclame cached data to free specified size on drive
        search: Discover cache with a full disk search
    """
    logger = None

    global detailer, verifier, watcher
    detailer = Detail(detail, False)
    verifier = Verify(verify)
    watcher = Watch(progress)

    try:
        config = config_setup(context)
        logger = get_pbench_logger("pbench-tree-manager", config)
        cache_m = CacheManager(config, logger)
        if display:
            verifier.status("starting discovery")
            watcher.update("discovering cache")
            cache_m.full_discovery(search=search)
            verifier.status("finished discovery")
            watcher.update("building report")
            print_tree(cache_m)
            rv = 0
        if reclaim_percent or reclaim_size:
            verifier.status("starting reclaim")
            watcher.update("reclaiming")
            target_size = humanfriendly.parse_size(reclaim_size) if reclaim_size else 0
            target_pct = reclaim_percent if reclaim_percent else 20.0
            outcome = cache_m.reclaim_cache(goal_pct=target_pct, goal_bytes=target_size)
            verifier.status(
                f"finished reclaiming: goal {''if outcome else 'not '}achieved"
            )
            rv = 0 if outcome else 1
    except Exception as exc:
        if logger:
            logger.exception("An error occurred discovering the file tree: {}", exc)
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
