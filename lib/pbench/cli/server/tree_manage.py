"""pbench-show-tree"""

from pathlib import Path
from typing import List

import click

from pbench.cli.server import config_setup, pass_cli_context
from pbench.cli.server.options import common_options
from pbench.common.logger import get_pbench_logger
from pbench.server import BadConfig
from pbench.server.api.resources.upload_api import Upload
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.users import User
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


@click.command()
@pass_cli_context
@click.option("--controller", help="Controller name for a created dataset")
@click.option(
    "--create",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True
    ),
    prompt="Tarball path",
    prompt_required=False,
    help="Create a dataset from a tarball and MD5 file",
)
@click.option(
    "--display", default=False, is_flag=True, help="Display the full tree on completion"
)
@click.option(
    "--full/--no-full", default=False, help="Discover the full tree on startup"
)
@click.option("--user", help="Username to own a created dataset")
@common_options
def tree_manage(
    context: object, controller: str, create: str, display: bool, full: bool, user: str
):
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

    Args:
        context: Click context (contains shared `--config` value)
        controller: Controller name (required for `--create`)
        create: Create a new on-disk dataset from a tarball path
        display: Print a simplified representation of the hierarchy
        full: Discover the full Pbench on-disk hierarchy
        user: Username to own a new dataset
    """
    try:
        config = config_setup(context)
        logger = get_pbench_logger("filetree", config)

        file_tree = FileTree(config, logger)
        if full:
            file_tree.full_discovery()

        if create:
            if not controller:
                click.echo("Create requires a controller name", err=True)
                exit(1)
            if not user:
                click.echo("Create requires a username", err=True)
                exit(1)
            owner = User.query(username=user)
            dataset = Dataset.create(controller=controller, owner=owner, path=create)
            tarball = file_tree.create(controller, Path(create))
            Upload.finalize_dataset(dataset, tarball, config, logger)

        if display:
            print_tree(file_tree)

        rv = 0
    except Exception as exc:
        logger.exception("Something went awry! {}", exc)
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
