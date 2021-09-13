#!/usr/bin/env python3
# -*- mode: python -*-

# Forward tar balls received via SSH from version 002 clients
# to the configured pbench server using the pbench agent's new
# PUT API interface.

import os
import sys
import tempfile

from pbench import PbenchConfig, BadConfig, get_pbench_logger
from pbench.process_tb import ProcessTb
from pbench.report import Report


_NAME_ = "pbench-server-put-shim"


def main(cfg_name: str) -> int:
    if not cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable",
            file=sys.stderr,
        )
        return 2

    try:
        config = PbenchConfig(cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e} (config file {cfg_name})", file=sys.stderr)
        return 1

    logger = get_pbench_logger(_NAME_, config)

    try:
        ptb = ProcessTb(config, logger)
    except Exception as e:
        logger.error("Error: {}", e)
        return 2

    counts = ptb.process_tb()

    result_string = (
        f"{config.TS} Status: Total no. of tarballs {counts.ntotal},"
        f" Successfully moved {counts.ntbs}, Encountered"
        f" {counts.nerr} Errors"
    )
    logger.info(result_string)

    # prepare and send report
    try:
        fd, tmp_file = tempfile.mkstemp(dir=config.TMP, text=True)
    except Exception as exc:
        logger.error("Creation of temporary Report file Failed: '{}'", exc)
        return 1

    try:
        with os.fdopen(fd, "w+") as reportfp:
            reportfp.write(f"{counts.nstatus}{result_string}\n")

        report = Report(config, _NAME_)
        report.init_report_template()
        report.post_status(config.timestamp(), "status", tmp_file)
    except Exception as exc:
        logger.warning("Report post unsuccessful: '{}'", exc)
    finally:
        os.remove(tmp_file)

    if counts.nerr > 0:
        return 1
    return 0


if __name__ == "__main__":
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    status = main(cfg_name)
    sys.exit(status)
