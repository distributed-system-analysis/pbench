#!/usr/bin/env python3
# -*- mode: python -*-

"""Import existing tarballs from the server filesystem into the Dataset
   tracking database.

   This is primarily useful for testing, to avoid a lot of manual effort
   when installing new code on a server VM with existing data.

   A typical workflow might be:

   1. Shut down pbench cron
   2. `yum erase pbench-server`
   3. Go to Postman and DELETE all templates and indices for server prefix
   4. Run psql and `drop database <db>` to start from scratch
   5. Install new server
   6. Copy pbench-server.cfg file to /opt/pbench-server/lib/config
   7. Run ansible config script
   8. Start pbench cron
   9. Run this script
  10. Run /opt/pbench-server/bin/pbench-reindex "date" "date" to trigger a
      full re-index.
"""

import glob
import os
import sys
from argparse import ArgumentParser, Namespace
from logging import Logger
from pathlib import Path
from typing import Generator

from pbench import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.database.models.tracker import Dataset, States, DatasetNotFound
from pbench.server.database.models.users import User


_NAME_ = "pbench-import-datasets"


class Import:
    def __init__(self, logger: Logger, options: Namespace, config: PbenchServerConfig):
        self.logger = logger
        self.options = options
        self.config = config
        self.errors = 0
        self.processed = 0

    def _collect_tb(self, link: str) -> Generator[str]:
        """Generator to return tarballs in a specified "state"

        Params:
            :link:  The Pbench "state" link directory name to search; e.g.,
                    TO-INDEX

        Generates:
            tarball names linked under the specified link name

        FIXME: This is taken almost intact from indexing_tarballs.py; but that
        would have required creating an indexer.py IdxCtx to initialize, which is
        too heavyweight for this context, and I don't really have any interest in
        quarantining files here (we do that many other places). I've always wanted
        to factor out a simpler "Pbench file system" class that would represent
        the identity, location, and state of each dataset; such a class could be
        reused here, in the indexer, in the audit checker, and elsewhere.
        """
        # find -L $ARCHIVE/*/$linksrc -name '*.tar.xz' -printf "%s\t%p\n" 2>/dev/null | sort -n > $list
        logger = self.logger
        archive = self.config.ARCHIVE
        tb_glob = os.path.join(archive, f"*/{link}/*.tar.xz")
        for tb in glob.iglob(tb_glob):
            try:
                rp = Path(tb).resolve(strict=True)
            except OSError:
                logger.warning("{} does not resolve to a real path", tb)
                continue
            controller_path = rp.parent
            archive_path = controller_path.parent
            if str(archive_path) != str(archive):
                logger.warning("For tar ball {}, original home is not {}", tb, archive)
                continue
            if not Path(f"{rp}.md5").is_file():
                logger.warning("Missing .md5 file for {}", tb)
                # Audit should pick up missing .md5 file in ARCHIVE directory.
                continue
            yield rp

    def process(self, link: str, state: States) -> int:
        """
        process Create Dataset records for pre-existing server tarballs that
        are in a specified filesystem "state" (the link directory in the
        archive tree), in a specified Dataset state.

        Each tarball for which a Dataset record already exists is IGNORED,
        and we don't attempt to advance the state.

        Args:
            :link (str):        Filesystem "state" link directory
                                (e.g., TO-INDEX)
            :state (States):    A state enum value representing desired Dataset
                                state.

        Returns:
            int: Status (0 success, 1 failure)
        """
        logger = self.logger
        done = 0
        fail = 0
        ignore = 0
        args = {}
        owner = User.validate_user(self.options.user)

        for tarball in self._collect_tb(link):
            if self.options.verify:
                print(f"Processing {tarball} from {link} -> state {state}")
            try:
                args["path"] = tarball
                try:
                    dataset = Dataset.attach(**args)
                    if self.options.verify:
                        print(f"Found existing {dataset}: {dataset.state}")
                    ignore = ignore + 1
                except DatasetNotFound:
                    a = args.copy()
                    a["md5"] = open(f"{tarball}.md5").read().split()[0]

                    # NOTE: including "state" on attach above would attempt to
                    # advance the dataset's state, which we don't want for
                    # import, so we add it only here. "owner" would be ignored
                    # by attach, but we add it here anyway for clarity.
                    a["state"] = state
                    a["owner"] = owner
                    dataset = Dataset.create(**a)
                    print(f"Imported {dataset}: {state}")
                    done = done + 1
            except Exception as e:
                # Stringify any exception and report it; then fail
                logger.exception("Import of dataset {} failed", tarball)
                print(f"{_NAME_}: dataset {tarball} failed with {e}", file=sys.stderr)
                fail = fail + 1
        print(
            f"Imported {done} datasets from {link} with {fail} errors and {ignore} ignored"
        )
        return 1 if fail > 0 else 0


def main(options):
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
    init_db(config, logger)

    # NOTE: the importer will ignore datasets that already exist in the DB;
    # we do the ACTION links first to get set up, and then sweep other links
    # to record the state of remaining datasets, especially to record those
    # which are quarantined.
    #
    # FIXME: This doesn't sweep the "<root>/quarantine" directory, which might
    # have additional datasets. Are they worth importing?
    actions = {
        "TO-UNPACK": States.UPLOADED,
        "TO-INDEX": States.UNPACKED,
        "INDEXED": States.INDEXED,
        "UNPACKED": States.UNPACKED,
        "WONT-UNPACK": States.QUARANTINED,
        "WONT-INDEX*": States.QUARANTINED,
        "BAD-MD5": States.QUARANTINED,
    }

    importer = Import(logger, options, config)

    return_value = 0
    for link, state in actions.items():
        status = importer.process(link, state)
        if status != 0:
            return_value = 1
    return return_value


if __name__ == "__main__":
    parser = ArgumentParser(
        prog=_NAME_, description="Import existing tarballs into the dataset database"
    )
    parser.add_argument(
        "-C",
        "--config",
        dest="cfg_name",
        default=os.environ.get("_PBENCH_SERVER_CONFIG"),
        help="Specify config file",
    )
    parser.add_argument(
        "--path",
        dest="path",
        help="Specify a tarball filename (from which controller and name will be derived)",
    )
    parser.add_argument(
        "--user",
        dest="user",
        required=True,
        help="Specify the owning username for the dataset",
    )
    parser.add_argument(
        "--verify", "-v", dest="verify", action="store_true", help="Show progress"
    )
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
