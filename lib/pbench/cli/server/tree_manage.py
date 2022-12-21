import click

from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup
from pbench.cli.server.options import common_options
from pbench.server import BadConfig
from pbench.server.cache_manager import CacheManager
from pbench.server.globals import server


def print_tree(tree: CacheManager):
    print(f"Tree anchored at {tree.archive_root}\n")

    if len(tree.datasets) == 0 and len(tree.controllers) == 0:
        print("Pbench file tree is empty")
        return

    print("Tarballs:")
    for tarball in tree.datasets.values():
        print(f"  {tarball.name}")

    print("\nControllers:")
    for controller in tree.controllers.values():
        print(f"  Controller {controller.name}:")
        for tarball in controller.tarballs.values():
            print(f"    Tarball {tarball.name}")
            if tarball.unpacked:
                print(f"      Unpacked in {tarball.unpacked}")


@click.command(name="pbench-tree-manager")
@pass_cli_context
@click.option(
    "--display", default=False, is_flag=True, help="Display the full tree on completion"
)
@common_options
def tree_manage(context: object, display: bool):
    """
    Discover, display, and manipulate the on-disk representation of controllers
    and datasets.

    This primarily exposes the CacheManager object hierarchy, and provides a simple
    hierarchical display of controllers and datasets.
    \f

    Args:
        context: Click context (contains shared `--config` value)
        display: Print a simplified representation of the hierarchy
    """
    try:
        config_setup(context, "cachemanager")
        cache_m = CacheManager()
        cache_m.full_discovery()
        if display:
            print_tree(cache_m)
        rv = 0
    except Exception as exc:
        server.logger.exception("An error occurred discovering the file tree: {}", exc)
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
