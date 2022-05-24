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
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.database.models.datasets import Dataset, States


_NAME_ = "pbench-state-manager"


def main(options):
    try:
        if not options.cfg_name:
            print(
                f"{_NAME_}: ERROR: No config file specified; set"
                " _PBENCH_SERVER_CONFIG env variable",
                file=sys.stderr,
            )
            return 2

        try:
            config = PbenchServerConfig(options.cfg_name)
        except BadConfig as e:
            print(f"{_NAME_}: {e}", file=sys.stderr)
            return 2

        logger = get_pbench_logger(_NAME_, config)

        # We're going to need the Postgres DB to track dataset state, so setup
        # DB access.
        init_db(config, logger)

        args = {}
        if options.create:
            args["owner"] = options.create

        if options.path:
            args["name"] = Dataset.stem(options.path)
        elif options.name:
            args["name"] = options.name
        if options.md5:
            args["md5"] = options.md5
        if options.state:
            try:
                new_state = States[options.state.upper()]
            except KeyError:
                print(
                    f"{_NAME_}: Specified string '{options.state}' is not a Pbench dataset state",
                    file=sys.stderr,
                )
                return 2
            args["state"] = new_state

        if "path" not in args and "name" not in args:
            print(
                f"{_NAME_}: Either --path or --name must be specified",
                file=sys.stderr,
            )
            return 2

        # Either create a new dataset or attach to an existing dataset
        doit = Dataset.create if options.create else Dataset.attach

        # Find or create the specified dataset.
        doit(**args)
    except Exception as e:
        # Stringify any exception and report it; then fail
        logger.exception("Failed")
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 1
    else:
        return 0


if __name__ == "__main__":
    parser = ArgumentParser(prog=_NAME_, description="Create a new dataset record")
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
        action="store",
        type=str,
        help="Specify owning user to create a new Dataset",
    )
    parser.add_argument(
        "--path",
        dest="path",
        help="Specify a tarball filename (from which controller and name will be derived)",
    )
    parser.add_argument(
        "--name",
        dest="name",
        help="Specify dataset name",
    )
    parser.add_argument(
        "--state",
        dest="state",
        help="Specify desired dataset state",
    )
    parser.add_argument("--md5", dest="md5", help="Specify dataset MD5 hash")
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
