#!/usr/bin/env python3
# -*- mode: python -*-

"""Command line interface to the Dataset state mechanism.

This serves two purposes:

1. It allows access to the state tracker for bash scripts;
2. It's used to pre-set database state for the `gold` unit tests

Therefore, while this can eventually be removed, we need to resolve both
of those requirements first.
"""

import sys
import os

from argparse import ArgumentParser

from pbench import BadConfig
from pbench.server import PbenchServerConfig
from pbench.server.database.models.tracker import Dataset, States
from pbench.server.database.database import Database
from pbench.common.logger import get_pbench_logger


_NAME_ = "pbench-state-manager"


def main(options):
    try:
        if not options.cfg_name:
            print(
                f"{_NAME_}: ERROR: No config file specified; set"
                " _PBENCH_SERVER_CONFIG env variable",
                file=sys.stderr,
            )
            return 1

        try:
            config = PbenchServerConfig(options.cfg_name)
        except BadConfig as e:
            print(f"{_NAME_}: {e}", file=sys.stderr)
            return 2

        logger = get_pbench_logger(_NAME_, config)

        # We're going to need the Postgres DB to track dataset state, so setup
        # DB access.
        Database.init_db(config, logger)

        args = {}
        if options.user:
            args["user"] = options.user
        if options.controller:
            args["controller"] = options.controller
        if options.path:
            args["path"] = options.path
        if options.name:
            args["name"] = options.name
        if options.state:
            try:
                new_state = States[options.state.upper()]
            except KeyError:
                print(
                    f"{_NAME_}: Specified string '{options.state}' is not a Pbench dataset state",
                    file=sys.stderr,
                )
                return 1
            args["state"] = new_state

        if "path" not in args and ("controller" not in args or "name" not in args):
            print(
                f"{_NAME_}: Either --path or both --controller and --name must be specified",
                file=sys.stderr,
            )
            return 1

        # Either create a new dataset or attach to an existing dataset
        doit = Dataset.create if options.create else Dataset.attach

        # Find the specified dataset, and update the state
        doit(**args)
    except Exception as e:
        # Stringify any exception and report it; then fail
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 1
    else:
        return 0


if __name__ == "__main__":
    parser = ArgumentParser(f"Usage: {_NAME_} [--config <path-to-config-file>]")
    parser.add_argument(
        "-C",
        "--config",
        dest="cfg_name",
        default=os.environ.get("_PBENCH_SERVER_CONFIG"),
        help="Specify config file",
    )
    parser.add_argument(
        "-c",
        "--create",
        dest="create",
        action="store_true",
        help="Create dataset instead of attaching to an existing dataset.",
    )
    parser.add_argument(
        "--path",
        dest="path",
        help="Specify a tarball filename (from which controller and name will be derived)",
    )
    parser.add_argument(
        "--user", dest="user", help="Specify the owning username for the dataset",
    )
    parser.add_argument(
        "--controller",
        dest="controller",
        help="Specify controller name (agent host name)",
    )
    parser.add_argument(
        "--name", dest="name", help="Specify dataset name",
    )
    parser.add_argument(
        "--state", dest="state", help="Specify desired dataset state",
    )
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
