from typing import List

import click

from pbench.cli.server import CliContext, config_setup, pass_cli_context
from pbench.cli.server.options import common_options
from pbench.common.logger import get_pbench_logger
from pbench.server import BadConfig
from pbench.server.filetree import FileTree


def print_tree(tree: FileTree):
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
                states: List[str] = []
                for name, path in controller.state_dirs.items():
                    for link in path.iterdir():
                        if tarball.name in link.name:
                            states.append(name)
                if states:
                    states.sort()
                    print(f"        States: {', '.join(states)}")


@click.group("pbench-tree-manage")
@pass_cli_context
@common_options
@click.option(
    "--display", default=False, is_flag=True, help="Display the full tree on completion"
)
@click.option(
    "--full-discovery",
    default=False,
    is_flag=True,
    help="Fully discovery file tree before performing requested operation",
)
@click.option(
    "--verify", default=False, is_flag=True, help="Show extra status messages"
)
def tree_manage(context: CliContext, display: bool, full_discovery: bool, verify: bool):
    """
    Discover, display, and manipulate the on-disk representation of controllers
    and datasets.

    This primarily exposes the FileTree object hierarchy, and provides a simple
    hierarchical display of controllers and datasets.
    \f

    Args:
        context: Click context (contains shared `--config` value)
        display: Print a simplified representation of the hierarchy
        full_discovery: Fully discover the file tree before starting
    """
    context.display = display
    context.full_discovery = full_discovery
    context.verify = verify
    try:
        context.config = config_setup(context)
        logger = get_pbench_logger("filetree", context.config)
        context.logger = logger
        file_tree = FileTree(context.config, logger)
        if context.full_discovery:
            file_tree.full_discovery()
        context.file_tree = file_tree
    except Exception as exc:
        logger.exception("An error occurred discovering the file tree: {}", exc)
        click.echo(exc, err=True)
        return 2 if isinstance(exc, BadConfig) else 1


@tree_manage.command()
@pass_cli_context
def list(context: object):
    """
    Display the contents of the file tree.

    The `--display` and `--full-discovery` options are allowed but enabled by
    default in this context.
    \f

    Args:
        context: Click context (contains shared `--config` value)
    """
    file_tree = context.file_tree

    # There's no point in displaying without discovery, so discover the tree
    # if we haven't already.
    if not context.full_discovery:
        file_tree.full_discovery()

    print_tree(file_tree)
    return 0
