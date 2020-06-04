#!/usr/bin/env python3
# -*- mode: python -*-

import logging
import os
import sys

from pbench import PbenchConfig
from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger

_NAME_ = "pbench-logger-level-test"
cfg_name = os.environ["_PBENCH_SERVER_CONFIG"]
logdir = os.environ["LOGSDIR"]

log_files = {
    "NOTSET": "notset.log",
    "DEBUG": "debug.log",
    "INFO": "info.log",
    "WARNING": "warn.log",
    "ERROR": "error.log",
    "CRITICAL": "critical.log",
}

log_msgs = {
    "0": "logging_level = NOTSET",
    "10": "logging_level = DEBUG",
    "20": "logging_level = INFO",
    "30": "logging_level = WARNING",
    "40": "logging_level = ERROR",
    "50": "logging_level = CRITICAL",
}


def mock_the_handler(logger, logging_level, fname):

    # logger.logger is used: the first logger is used to format
    # the logs with the help of _styleAdapter and the second is
    # used to log the messages
    fh = logging.FileHandler(os.path.join(logdir, fname))
    fh.setLevel(logging_level)
    logger.logger.addHandler(fh)

    return logger


def test_pbench_logger_level():

    config = PbenchConfig(cfg_name)
    logger = get_pbench_logger(_NAME_, config)

    logging_level = config.get("logging", "logging_level")

    logger = mock_the_handler(logger, logging_level, log_files[logging_level])

    logger.debug(log_msgs["10"])
    logger.info(log_msgs["20"])
    logger.warning(log_msgs["30"])
    logger.error(log_msgs["40"])
    logger.critical(log_msgs["50"])


if __name__ == "__main__":
    try:
        test_pbench_logger_level()
    except BadConfig as bd:
        print(f"BadConfig exception was raised, '{bd}'")
        sys.exit(1)
