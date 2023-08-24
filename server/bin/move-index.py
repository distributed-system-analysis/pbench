#!/usr/bin/env python3
# -*- mode: python -*-

"""Index migration utility (prototype)

This tool reads "server.index-map" metadata from datasets and converts them to
IndexMap model objects.
"""

from argparse import ArgumentParser
import os
from pathlib import Path
import re
import sys

from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Metadata
from pbench.server.database.models.index_map import IndexMap


def main(options, name):
    """Upgrade dataset index maps

    This will locate all datasets with archaic "server.index-map" metadata,
    convert each into a set of IndexMap rows, and optionally remove the
    "server.index-map" metadata.
    """
    # We're going to need the DB to track dataset state, so setup DB access.
    # We need to do this before we create the IdxContext, since that will
    # need the template DB; so we create a PbenchServerConfig and Logger
    # independently.
    config = PbenchServerConfig.create(options.cfg_name)
    logger = get_pbench_logger(name, config)
    init_db(config, logger)
    prefix = config.get("Indexing", "index_prefix")
    pattern = re.compile(rf"{prefix}\.v[0-9]+\.([a-z-]+)\.")
    idx = (
        Database.db_session.query(Metadata)
        .filter(Metadata.key == "server", Metadata.value["index-map"].is_not(None))
        .all()
    )
    new_maps = []
    datasets = set()
    roots = set()
    indices = 0
    documents = 0
    for m in idx:
        if m.value.get("index-map"):
            datasets.add(m.dataset)
            for i, d in m.value["index-map"].items():
                indices += 1
                match = pattern.match(i)
                root = match.group(1) if match else "<unknown>"
                roots.add(root)
                documents += len(d)
                ids = d[:4]
                if (len(d) - 4) > 0:
                    ids.append(f"...{len(d) - 4}")
                im = IndexMap(dataset=m.dataset, root=root, index=i, documents=ids)
                new_maps.append(im)
                if options.verify:
                    print(
                        f"IndexMap({im.dataset}, {im.root}, {im.index}, {im.documents})"
                    )
    if options.verify:
        print(
            f"{len(datasets)} datasets have {len(roots)} index roots "
            f"containing {indices} indices with {documents} documents"
        )
    if not options.preview:
        Database.db_session.add_all(new_maps)
        Database.db_session.commit()

        # We don't have a `Metadata.deletevalue`; instead, retain a null
        # index-map, which isn't harmful and if nothing else serves as a
        # (mostly useless) marker that this dataset was converted.
        if options.delete:
            for dataset in datasets:
                Metadata.setvalue(dataset, "server.index-map", None)
    return 0


###########################################################################
# Options handling
if __name__ == "__main__":
    run_name = Path(sys.argv[0]).name
    run_name = run_name if run_name[-3:] != ".py" else run_name[:-3]
    parser = ArgumentParser(f"Usage: {run_name} [--config <path-to-config-file>]")
    parser.add_argument(
        "-C",
        "--config",
        dest="cfg_name",
        default=os.environ.get(
            "_PBENCH_SERVER_CONFIG", "/opt/pbench-server/lib/config/pbench-server.cfg"
        ),
        help="Specify config file",
    )
    parser.add_argument(
        "-d",
        "--delete",
        dest="delete",
        action="store_true",
        help="Delete the 'server.index-map' metadata",
    )
    parser.add_argument(
        "-p",
        "--preview",
        dest="preview",
        action="store_true",
        help="Preview the operation but don't make changes",
    )
    parser.add_argument(
        "-v",
        "--verify",
        dest="verify",
        action="store_true",
        help="Print each IndexMap entry",
    )
    parsed = parser.parse_args()
    try:
        status = main(parsed, run_name)
    except Exception as e:
        status = 1
        print(f"Unexpected error {e}", file=sys.stderr)
    sys.exit(status)
