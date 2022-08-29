#!/usr/bin/env python3
# -*- mode: python -*-

"""Command line interface to the Dataset state mechanism.

This serves two purposes:

1. It allows access to the dataset SQL table for bash scripts;
2. It's used to pre-set database state for the `gold` unit tests

Therefore, while this can eventually be removed, we need to resolve both
of those requirements first.
"""

from argparse import ArgumentParser
import json
import os
import sys

from pbench import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.common.utils import md5sum
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.database.models.datasets import Dataset, Metadata, States
from pbench.server.sync import Operation, Sync

_NAME_ = "pbench-state-manager"


def main(options) -> int:
    try:
        config = PbenchServerConfig(options.cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 2

    logger = get_pbench_logger(_NAME_, config)

    try:
        if not options.cfg_name:
            print(
                f"{_NAME_}: ERROR: No config file specified; set"
                " _PBENCH_SERVER_CONFIG env variable",
                file=sys.stderr,
            )
            return 2

        # We're going to need the Postgres DB to track dataset state, so setup
        # DB access.
        init_db(config, logger)

        # Construct a sync object to manage dataset operational sequencing.
        sync = Sync(logger)

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
                list = sync.next(operator)
            except KeyError as e:
                print(
                    f"{_NAME_}: Specified operation {e!r} is not a valid operator.",
                    file=sys.stderr,
                )
                return 1

            for dataset in list:
                tarfile = Metadata.getvalue(dataset, Metadata.TARBALL_PATH)
                print(tarfile)

            return 0

        args = {}

        if options.md5:
            args["resource_id"] = options.md5
        elif options.path:
            args["resource_id"] = md5sum(options.path).md5_hash
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

        metadata = {}
        if options.set_metadata:
            for m in options.set_metadata:
                key, value = m.split("=")
                if not Metadata.is_key_path(key, Metadata.METADATA_KEYS):
                    print(
                        f"{_NAME_}: Set metadata key {key!r} is not valid",
                        file=sys.stderr,
                    )
                    return 2
                try:
                    encoded = json.loads(value)
                except Exception:
                    print(
                        f"{_NAME_}: Key {key!r} value {value!r} isn't valid JSON",
                        file=sys.stderr,
                    )
                    return 2
                if not (key and value):
                    print(
                        f"{_NAME_}: Can't set metadata {key!r} to value {value!r}",
                        file=sys.stderr,
                    )
                    return 2
                metadata[key] = encoded

        if options.get_metadata:
            for m in options.get_metadata:
                if not Metadata.is_key_path(m, Metadata.METADATA_KEYS):
                    print(
                        f"{_NAME_}: Get metadata key {m!r} is not valid",
                        file=sys.stderr,
                    )
                    return 2

        # Either create a new dataset or attach to an existing dataset
        doit = Dataset.create if options.create else Dataset.attach

        # Find or create the specified dataset.
        dataset = doit(**args)

        if operators or did:
            sync.update(dataset, did, operators)

        for key, value in metadata.items():
            Metadata.setvalue(dataset, key, value)

        for key in options.get_metadata:
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
        logger.exception("Failed to {} {}", what, args)
        print(f"{_NAME_}: {e}: {e.with_traceback(None)}", file=sys.stderr)
        return 1
    else:
        print("Finished successfully")
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
        "--did",
        dest="did",
        help=(
            "Specify a completed sequence operator to be removed from the"
            " pending set"
        ),
    )
    parser.add_argument(
        "--get-metadata",
        "-g",
        action="append",
        dest="get_metadata",
        help="Print metadata values as key=value",
    )
    parser.add_argument(
        "--set-metadata",
        "-m",
        action="append",
        dest="set_metadata",
        help="Specify metadata values to set as key=value",
    )
    parser.add_argument(
        "--name",
        dest="name",
        help="Specify dataset name",
    )
    parser.add_argument(
        "--operations",
        dest="operation",
        help=(
            "Specify sequence operators to trigger server behaviors: "
            "BACKUP, UNPACK, INDEX"
        ),
    )
    parser.add_argument(
        "--path",
        dest="path",
        help="Specify a tarball filename (from which controller and name will be derived)",
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
    parser.add_argument("--md5", dest="md5", help="Specify dataset MD5 hash")
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
