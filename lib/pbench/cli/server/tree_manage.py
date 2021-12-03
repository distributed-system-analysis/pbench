from typing import List

import click

from pbench.cli.server import config_setup, pass_cli_context
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

    This primarily exposes the FileTree object hierarchy, and provides a simple
    hierarchical display of controllers and datasets.

    This command can also be used to create a dataset, using the Dataset and
    FileTree classes to maintain equivalence with the PUT operation (skipping
    the network upload when the tarball and MD5 file are available locally). We
    don't implement `--delete` however, as that would require also integrating
    with the Elasticsearch bulk delete: this has to be done through the API.
    \f

    Args:
        context: Click context (contains shared `--config` value)
        display: Print a simplified representation of the hierarchy
    """
    try:
        config = config_setup(context)
        logger = get_pbench_logger("filetree", config)
        file_tree = FileTree(config, logger)
        file_tree.full_discovery()
        rv = 0
    except Exception as exc:
        logger.exception("An error occurred discovering the file tree: {}", exc)
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1
    else:
        if display:
            print_tree(file_tree)

    click.get_current_context().exit(rv)
