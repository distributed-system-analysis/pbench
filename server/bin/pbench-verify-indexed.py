#!/usr/libexec/platform-python
# -*- mode: python -*-

"""Pbench Verify Indexed

Review all archived tar balls and report how many have been properly indexed.
"""

import os
import re
import sys

from pathlib import Path
from argparse import ArgumentParser

from elasticsearch1 import Elasticsearch

import pbench


_NAME_ = "pbench-verify-indexed"

tb_pat_r = (
    r"\S+_(\d\d\d\d)[._-](\d\d)[._-](\d\d)[T_](\d\d)[._:](\d\d)[._:](\d\d)\.tar\.xz"
)
tb_pat = re.compile(tb_pat_r)


def gen_tb_list(archive):
    """gen_tb_list - yield all controller/tarball names
    """
    with os.scandir(archive) as archive_scan:
        # We are scanning the archive directory for all controller
        # sub-directories.
        for c_entry in archive_scan:
            if c_entry.name.startswith(".") and c_entry.is_dir(follow_symlinks=False):
                # Ignore any ".*" subdirectories.
                continue
            if not c_entry.is_dir(follow_symlinks=False):
                # NOTE: the pbench-audit-server should pick up and flag this
                # unwanted condition.
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
                        # tar ball pattern.  Such entries should be flagged by
                        # the server audit process.
                        continue
                    yield c_entry.name, entry.name


def main(options):
    if not options.cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable",
            file=sys.stderr,
        )
        return 1

    try:
        config = pbench.PbenchConfig(options.cfg_name)
    except pbench.BadConfig as e:
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 2

    try:
        archive_p = Path(config.ARCHIVE).resolve(strict=True)
    except FileNotFoundError:
        print(
            f"The configured ARCHIVE directory, {config.ARCHIVE}, does not exist",
            file=sys.stderr,
        )
        return 3

    if not archive_p.is_dir():
        print(
            f"The configured ARCHIVE directory, {config.ARCHIVE}, is not a valid directory",
            file=sys.stderr,
        )
        return 4

    print("Verifying indexed state of tar balls")
    start = pbench._time()

    es = Elasticsearch(
        [
            {
                "host": "elasticsearch.intlab.perf-infra.lab.eng.rdu2.redhat.com",
                "port": "10081",
                "timeout": 600,
            },
        ]
    )
    body = {
        "query": {
            "filtered": {
                "query": {"query_string": {"analyze_wildcard": True, "query": "*"}}
            }
        }
    }
    res = es.search(
        index="dsa-pbench.v4.run.*",
        doc_type="pbench-run",
        expand_wildcards="open",
        body=body,
        fields=["@metadata.file-name"],
        size=100000,
    )
    indexed = {}
    indexed_cnt = 0
    for hit in res["hits"]["hits"]:
        tb_file = hit["fields"]["@metadata.file-name"][0]
        assert tb_file not in indexed, f"Whoa, found a duplicate, f{tb_file}"
        if tb_file.startswith("/pbench/archive"):
            tb_file = f"/srv{tb_file}"
        indexed[tb_file] = False
        indexed_cnt += 1
    q_end = pbench._time()

    on_disk_cnt = 0
    on_disk_indexed_cnt = 0
    not_indexed = []
    for ctrl, tb_name in gen_tb_list(archive_p):
        tb_file = str(archive_p / ctrl / tb_name)
        on_disk_cnt += 1
        if tb_file in indexed:
            indexed[tb_file] = True
            on_disk_indexed_cnt += 1
        else:
            not_indexed.append(tb_file)
    assert len(not_indexed) == (on_disk_cnt - on_disk_indexed_cnt)

    not_on_disk_cnt = 0
    not_on_disk = []
    for key, val in indexed.items():
        if not val:
            not_on_disk_cnt += 1
            not_on_disk.append(key)
    end = pbench._time()

    print(f"On Disk: {on_disk_cnt:n}, indexed {on_disk_indexed_cnt:n}")
    print(f"Indexed: {indexed_cnt:n}, not on disk {not_on_disk_cnt:n}")
    print(f"Run-time: {start} {end} {end - start}, query time {q_end - start}")

    if not_on_disk:
        print(f"Not on disk... ({not_on_disk_cnt:n})")
        for tb_file in not_on_disk:
            print(f"\t{tb_file}")
    if not_indexed:
        print(f"Not indexed... ({(on_disk_cnt - on_disk_indexed_cnt):n})")
        for tb_file in not_indexed:
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
    status = main(parsed)
    sys.exit(status)
