#!/usr/bin/env python3
# -*- mode: python -*-

"""Command line interface to Dataset state.

This serves two purposes:

1. It allows access to the dataset and metadata operations for bash scripts;
2. It allows bash scripts to access the synchronization class

Most of this will become obsolete as we phase out bash scripts in the server
component pipeline.
"""

from argparse import ArgumentParser
import json
import os
import sys

from pbench import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.database.models.datasets import Dataset, Metadata, States
from pbench.server.sync import Operation, Sync
from pbench.server.utils import get_tarball_md5

_NAME_ = "pbench-state-manager"


def main(options) -> int:
    try:
        if not options.cfg_name:
            print(
                f"{_NAME_}: ERROR: No config file specified; set"
                " _PBENCH_SERVER_CONFIG env variable",
                file=sys.stderr,
            )
            return 2
        config = PbenchServerConfig(options.cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 2

    logger = get_pbench_logger(_NAME_, config)

    try:

        # We're going to need the Postgres DB to track dataset state, so setup
        # DB access.
        init_db(config, logger)

        # Construct a sync object to manage dataset operational sequencing.
        sync = Sync(logger, options.sync if options.sync else _NAME_)

        if options.query_operation:
            if (
                options.md5
                or options.path
                or options.name
                or options.create
                or options.state
            ):
                print(
                    f"{_NAME_}: No other options can be specified with --query-operation",
                    file=sys.stderr,
                )
                return 2
            try:
                operator = Operation[options.query_operation.upper()]
                datasets = sync.next(operator)
            except KeyError as e:
                print(
                    f"{_NAME_}: Specified operation {e!r} is not a valid operator.",
                    file=sys.stderr,
                )
                return 1

            for dataset in datasets:
                tarfile = Metadata.getvalue(dataset, Metadata.TARBALL_PATH)
                print(tarfile)

            return 0

        args = {}

        if options.md5:
            args["resource_id"] = options.md5
        elif options.path:
            args["resource_id"] = get_tarball_md5(options.path)
        else:
            print(
                f"{_NAME_}: Either --path or --md5 must be specified",
                file=sys.stderr,
            )
            return 2

        if options.create:
            args["owner"] = options.create
            if options.name:
                args["name"] = options.name
            elif options.path:
                args["name"] = Dataset.stem(options.path)
            else:
                print(
                    f"{_NAME_}: Either --path or --name must be specified with --create",
                    file=sys.stderr,
                )
                return 2

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

        if options.did:
            try:
                did = Operation[options.did.upper()]
            except KeyError as e:
                print(
                    f"{_NAME_}: Specified string is not a valid operator: {e}",
                    file=sys.stderr,
                )
                return 2
        else:
            did = None

        if options.operation:
            try:
                operators = [Operation[o.upper()] for o in options.operation.split(",")]
            except KeyError as e:
                print(
                    f"{_NAME_}: Specified string is not a valid operator: {e}",
                    file=sys.stderr,
                )
                return 2
        else:
            operators = None

        set_metadata = {}
        if options.set_metadata:
            for m in options.set_metadata:
                key, value = m.split("=", 1)
                if not Metadata.is_key_path(key, Metadata.METADATA_KEYS):
                    print(
                        f"{_NAME_}: Set metadata key {key!r} is not valid",
                        file=sys.stderr,
                    )
                    return 2

                if value.startswith("{"):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError as e:
                        print(
                            f"{_NAME_}: Can't decode JSON value {value!r} for {key!r}: {e}",
                            file=sys.stderr,
                        )
                        return 1
                set_metadata[key] = value

        get_metadata = []
        if options.get_metadata:
            for metaval in options.get_metadata:
                for m in metaval.split(","):
                    if not Metadata.is_key_path(m, Metadata.METADATA_KEYS):
                        print(
                            f"{_NAME_}: Get metadata key {m!r} is not valid",
                            file=sys.stderr,
                        )
                        return 2
                    get_metadata.append(m)

        # Either create a new dataset or attach to an existing dataset
        doit = Dataset.create if options.create else Dataset.attach

        # Find or create the specified dataset.
        dataset = doit(**args)

        if did or operators or options.error:
            sync.update(
                dataset=dataset, did=did, enabled=operators, status=options.error
            )

        for key, value in set_metadata.items():
            print(f"Setting {key!r}={value!r}")
            Metadata.setvalue(dataset, key, value)

        for key in get_metadata:
            v = Metadata.getvalue(dataset, key)
            print(f"{key}={v}")

    except Exception as e:
        # Stringify any exception and report it; then fail
        what = (
            "create"
            if options.create
            else f"Find operator {options.query_operation}"
            if options.query_operation
            else "attach"
        )
        logger.exception("Failed to {} {}", what, options)
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
        help="Specify owning username to create a new Dataset",
    )
    parser.add_argument(
        "--did",
        dest="did",
        help=(
            "Specify a completed dataset operator to be removed from the" " pending set"
        ),
    )
    parser.add_argument(
        "--error",
        dest="error",
        help=("Specify an error message to be recorded" " for a dataset"),
    )
    parser.add_argument(
        "-g",
        "--get-metadata",
        action="append",
        dest="get_metadata",
        help=(
            "Print metadata values for a specified comma-separate list "
            "of keys. This option can be repeated."
        ),
    )
    parser.add_argument(
        "-m",
        "--set-metadata",
        action="append",
        dest="set_metadata",
        help=(
            "Specify a metadata value to set as key=value. "
            "This option can be repeated to set multiple keys"
        ),
    )
    parser.add_argument(
        "--name",
        dest="name",
        help="Specify the dataset name",
    )
    parser.add_argument(
        "--operations",
        dest="operation",
        help=(
            "Specify sequence operators to trigger server behaviors: "
            "for example, 'BACKUP,UNPACK,INDEX'"
        ),
    )
    parser.add_argument(
        "--path",
        dest="path",
        help=(
            "Specify a tarball file path (from which " "a dataset name will be derived)"
        ),
    )
    parser.add_argument(
        "--query-operation",
        dest="query_operation",
        help="Return a list of tarball paths with the designated pending operation",
    )
    parser.add_argument(
        "--state",
        dest="state",
        help="Specify desired dataset state",
    )
    parser.add_argument(
        "--sync",
        dest="sync",
        help="Specify a name for the 'sync' object used for --query_operation, "
        "--operations, --did, and --error",
    )
    parser.add_argument("--md5", dest="md5", help="Specify dataset MD5 hash")
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
