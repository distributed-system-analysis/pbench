#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench indexing driver, responsible for indexing a single pbench tar ball
into the configured Elasticsearch instance.

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


def main(options, name):
    """Upgrade dataset index maps

    This will locate all datasets with archaic "server.index-map" metadata,
    convert each into a set of IndexMap rows, and optionally remove the
    "server.index-map" metadata.

    TODO: This is a prototype. Right now, it'll identify all `server.index-map`
    metadata and *print* an `IndexMap` constructor. In reality this will need
    to be run on a server with the new index map table defined and datasets
    with the old server.index-map metadatas. E.g., run on the staging server,
    this produces output like

    IndexMap((dbutenho)|uperf_test3_2023.07.18T17.20.54, result-data, stage-pbench.v5.result-data.2023-07-18, ['589c48e60d4f55160f7c743b9e19950d', 'ce192075a2cd84458a569f0c0c4fb7be', '3ebae5afe2df975fe6ae824fc991a348', '7f60702e2d458bc0aecc74221d9d7376', '...898'])
    IndexMap((wscales)|pbench-user-benchmark_example-workload_2023.07.28T17.12.42, run-data, stage-pbench.v6.run-data.2023-07, ['4791ba8750d960fd241b38c9ef912f80'])
    IndexMap((wscales)|pbench-user-benchmark_example-workload_2023.07.28T17.12.42, run-toc, stage-pbench.v6.run-toc.2023-07, ['227d9bf9538db594c8cd6754eddac917', 'ad4c2e99fc31d731b61a3c0433267580', '2b5ba1a77e975da064adfc031ae83c52', '7d84631503094c810b1a5f2e71b26e28', '...11'])
    IndexMap((wscales)|pbench-user-benchmark_example-workload_2023.07.28T17.20.09, run-data, stage-pbench.v6.run-data.2023-07, ['3fc5c4615ec46a43fc6c158b4b6eaab8'])
    IndexMap((wscales)|pbench-user-benchmark_example-workload_2023.07.28T17.20.09, run-toc, stage-pbench.v6.run-toc.2023-07, ['b8a5d8400b7607434c91e88942afaeda', '200cb623169ec98170c850097d7274c7', '99bc05751057291f2e0621375e2af1ce', 'bd967420d190aff9143140f5bedcb351', '...11'])

    Catch-22:

    This is only in the commit as an example, and possibly shouldn't be merged.
    I can't modify it to create actual IndexMap records on the staging server
    until we deploy, and on a runlocal server it'll find no server.index-map
    metadata.
    """
    # We're going to need the DB to track dataset state, so setup DB access.
    # We need to do this before we create the IdxContext, since that will
    # need the template DB; so we create a PbenchServerConfig and Logger
    # independently.
    config = PbenchServerConfig.create(options.cfg_name)
    logger = get_pbench_logger(name, config)
    init_db(config, logger)
    prefix = config.get("Indexing", "index_prefix")
    pattern = re.compile(f"{prefix}\\.v[0-9]+\\.([a-z-]+)\\.")
    idx = (
        Database.db_session.query(Metadata)
        .filter(Metadata.key == "server", Metadata.value["index-map"].is_not(None))
        .all()
    )
    for m in idx:
        for i, d in m.value["index-map"].items():
            match = pattern.match(i)
            if match:
                root = match.group(1)
            else:
                root = "<unknown>"
            ids = d[:4]
            if (len(d) - 4) > 0:
                ids.append(f"...{len(d) - 4}")
            print(f"IndexMap({m.dataset}, {root}, {i}, {ids})")
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
    parsed = parser.parse_args()
    try:
        status = main(parsed, run_name)
    except Exception as e:
        status = 1
        print(f"Unexpected error {e}", file=sys.stderr)
    sys.exit(status)
