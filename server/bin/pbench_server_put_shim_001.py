#!/usr/bin/env python3
# -*- mode: python -*-

# This script is used to send the tarballs that a version 002 client
# submits for further processing. It forwards the tarballs and their MD5
# sums to the remote server using the server's HTTP PUT method

import glob
import os
import sys
import tempfile
import urllib.parse

from collections import namedtuple
from logging import Logger
from pathlib import Path

from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.common.results import CopyResultTb
from pbench.common.utils import md5sum
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.report import Report


_NAME_ = "pbench-server-put-shim-001"

Results = namedtuple("Results", ["nstatus", "ntotal", "ntbs"])


def get_receive_dir(config: PbenchServerConfig, logger: Logger) -> Path:

    receive_dir_prefix = config.get("pbench-server", "pbench-receive-dir-prefix")
    if not receive_dir_prefix:
        logger.error(
            "Failed: No value for config option pbench-receive-dir-prefix in section pbench-server"
        )
        return None

    receive_dir = Path(f"{receive_dir_prefix}-002").resolve()
    if not receive_dir.is_dir():
        logger.error("Failed: {} does not exist, or is not a directory", receive_dir)
        return None

    return receive_dir


def process_tb(
    config: PbenchServerConfig, logger: Logger, receive_dir: Path
) -> Results:
    """process_tb - receives a tar ball and copies it to the remote server
                    using the server's HTTP PUT method

        Args -
            config -- PbenchServer config object
            logger -- logger object to use when emitting log entries during
                      operation
            receive_dir -- directory where tarballs are received from agent

    """

    # Check for results that are ready for processing: version 002 agents
    # upload the MD5 file as xxx.md5.check and they rename it to xxx.md5
    # after they are done with MD5 checking so that's what we look for.
    list_check = glob.glob(
        os.path.join(receive_dir, "**", "*.tar.xz.md5"), recursive=True
    )

    logger.info("{}", config.TS)
    list_check.sort()
    nstatus = ""

    ntotal = ntbs = 0

    token = config.get("pbench-server", "put-token")

    for tbmd5 in list_check:
        ntotal += 1

        # Extracts full pathname of tarball from the name of hashfile
        # by trimming .md5 suffix
        tb = Path(tbmd5[0 : -len(".md5")])
        tbmd5 = Path(tbmd5)
        tbdir = tb.parent
        controller = tbdir.name
        server_rest_url = config.get("results", "server_rest_url")
        tbname = urllib.parse.quote(tb.name)
        upload_url = f"{server_rest_url}/upload/{tbname}"

        try:
            tarball_len, tarball_md5 = md5sum(tb)

            crt = CopyResultTb(
                controller, tb, tarball_len, tarball_md5, upload_url, logger,
            )
            crt.copy_result_tb(token)
        except Exception as e:
            logger.error("{}: Unexpected Error: {}", config.TS, e)
            continue

        try:
            os.remove(tbmd5)
            os.remove(tb)
        except Exception as exc:
            logger.error(
                "{}: Warning: cleanup of successful copy operation failed: '{}'",
                config.TS,
                exc,
            )

        ntbs += 1

        nstatus = f"{nstatus}: processed {tb}\n"
        logger.info(f"{tb.name}: OK")

    return Results(nstatus, ntotal, ntbs)


def main(cfg_name: str) -> int:
    if not cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable or use --config <file> on the"
            " command line",
            file=sys.stderr,
        )
        return 2

    try:
        config = PbenchServerConfig(cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e} (config file {cfg_name})", file=sys.stderr)
        return 1

    logger = get_pbench_logger(_NAME_, config)
    init_db(config, logger)

    receive_dir = get_receive_dir(config, logger)

    if receive_dir is None:
        return 2

    counts = process_tb(config, logger, receive_dir)

    result_string = (
        f"{config.TS} Status: Total no. of tarballs {counts.ntotal},"
        f" Successfully moved {counts.ntbs}, Encountered"
        f" {counts.ntotal-counts.ntbs} failures"
    )
    logger.info(result_string)

    # prepare and send report
    with tempfile.NamedTemporaryFile(mode="w+t", dir=config.TMP) as reportfp:
        reportfp.write(f"{counts.nstatus}{result_string}\n")
        reportfp.seek(0)

        report = Report(config, _NAME_)
        report.init_report_template()
        try:
            report.post_status(config.timestamp(), "status", reportfp.name)
        except Exception as exc:
            logger.warning("Report post Unsuccesful: '{}'", exc)

    return 0


if __name__ == "__main__":
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    status = main(cfg_name)
    sys.exit(status)
