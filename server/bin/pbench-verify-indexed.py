#!/usr/libexec/platform-python
# -*- mode: python -*-

"""Pbench Verify Indexed

Review all archived tar balls and report how many have been properly indexed.
"""
import logging
import os
import re
import sys
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path

import pbench
import pbench.indexer
from elasticsearch1 import Elasticsearch, helpers

_NAME_ = "pbench-verify-indexed"

tb_pat = re.compile(pbench.TAR_BALL_NAME_W_TAR_PAT_S)

# Number of JSON documents to fetch in one batch for the scan operation.
BATCH_SIZE = 10000


def gen_tb_list(archive):
    """Yield all controller/tarball name pairs found in the given archive
    directory.
    """
    with os.scandir(archive) as archive_scan:
        # We are scanning the archive directory for all controller
        # sub-directories.
        for c_entry in archive_scan:
            if not c_entry.is_dir(follow_symlinks=False):
                # Ignore any non-directories encountered, not our problem.
                continue
            if c_entry.name.startswith("."):
                # Ignore any ".*" subdirectories.
                continue
            # We have a controller directory, now we scan the controller
            # directory for all tar balls.
            with os.scandir(c_entry.path) as controller_scan:
                for entry in controller_scan:
                    if not entry.is_file(follow_symlinks=False):
                        # Tar balls can only be files.
                        continue
                    if entry.name.startswith("."):
                        # Ignore any files starting with ".".
                        continue
                    match = tb_pat.fullmatch(entry.name)
                    if not match:
                        # Ignore any directory entries which do not match the
                        # tar ball pattern.
                        continue
                    yield c_entry.name, entry.name


def main(options):
    """Simple driver function for this CLI.

    Prints a report summarizing what was found, and then provides detailed
    lists of properly and improperly indexed tar balls.

    Returns 0 on success, 1 on failure.
    """
    try:
        config = pbench.PbenchConfig(options.cfg_name)
    except pbench.BadConfig as e:
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 1

    try:
        archive_p = Path(config.ARCHIVE).resolve(strict=True)
    except FileNotFoundError:
        print(
            f"The configured ARCHIVE directory, {config.ARCHIVE}," " does not exist",
            file=sys.stderr,
        )
        return 1

    if not archive_p.is_dir():
        print(
            f"The configured ARCHIVE directory, {config.ARCHIVE},"
            " is not a valid directory",
            file=sys.stderr,
        )
        return 1

    es_client = Elasticsearch(
        pbench.indexer._get_es_hosts(config, logging.getLogger("pbench-verify-indexed"))
    )
    query = {"query": {"match_all": {}}}

    index_prefix = config.get("Indexing", "index_prefix")
    if not index_prefix:
        print(
            "Missing 'index_prefix' value in 'Indexing' section of configuration",
            file=sys.stderr,
        )
        return 1

    # Start the overall timer.
    start = pbench._time()
    start_s = pbench.tstos(start)
    print(f"[{start_s}] Verifying indexed state of tar balls", flush=True)

    # Fetch a batch of records at a time.
    scanner = helpers.scan(
        es_client,
        index=f"{index_prefix}.v4.run.*",
        doc_type="pbench-run",
        query=query,
        expand_wildcards="open",
        fields=["@metadata.file-name"],
        size=BATCH_SIZE,
    )
    indexed = defaultdict(int)
    for hit in scanner:
        tb_file_p = Path(hit["fields"]["@metadata.file-name"][0])
        tb_file = f"{tb_file_p.parent.name}/{tb_file_p.name}"
        indexed[tb_file] += 1
    indexed_cnt = len(indexed)

    # Look for duplicates in the returned Elasticsearch data to help detect
    # problems with the indexer.
    duplicates = []
    for tb_file, val in indexed.items():
        if val > 1:
            duplicates.append(tb_file)
    if duplicates:
        print(f"WARNING - encountered {len(duplicates):d} tar ball duplicate names")
        for dup in duplicates:
            print(f"\t{dup}")

    # Snap shot of query time.
    q_end = pbench._time()

    on_disk = defaultdict(int)
    on_disk_cnt = 0
    on_disk_indexed_cnt = 0
    not_indexed = []
    for ctrl, tb_name in gen_tb_list(archive_p):
        tb_file = f"{ctrl}/{tb_name}"
        on_disk[tb_file] += 1
        if tb_file in indexed:
            on_disk_indexed_cnt += 1
        else:
            not_indexed.append(tb_file)
    on_disk_cnt = len(on_disk)

    # Snap shot of disk scan time.
    d_end = pbench._time()

    not_on_disk = [f for f in indexed.keys() if f not in on_disk]
    not_on_disk_cnt = len(not_on_disk)

    # The heavy lifting is done.
    end = pbench._time()
    end_s = pbench.tstos(end)

    print(f"[{end_s}] Generating report ...")
    print(f"On Disk: {on_disk_cnt:n}, indexed {on_disk_indexed_cnt:n}")
    print(f"Indexed: {indexed_cnt:n}, not on disk {not_on_disk_cnt:n}")
    print(
        f"Run-time: {(end - start):.2f}s, query time {(q_end - start):.2f}s,"
        f" disk time {(d_end - q_end):.2f}s, final pass {(end - d_end):.2f}s"
    )

    if not_on_disk:
        print(f"Not on disk... ({not_on_disk_cnt:n})")
        for tb_file in sorted(not_on_disk):
            print(f"\t{tb_file}")
    if not_indexed:
        print(f"Not indexed... ({(on_disk_cnt - on_disk_indexed_cnt):n})")
        for tb_file in sorted(not_indexed):
            print(f"\t{tb_file}")

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
    parsed = parser.parse_args()
    if not parsed.cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified on command line via -C"
            " or --config, and the _PBENCH_SERVER_CONFIG env variable did not"
            " have a value",
            file=sys.stderr,
        )
        status = 1
    else:
        status = main(parsed)
    sys.exit(status)
