#!/usr/bin/env python3
# -*- mode: python -*-

import os, sys
import logging

from pbench import PbenchConfig, BadConfig, get_pbench_logger

_NAME_ = "pbench-logger-test"
cfg_name = os.environ["_PBENCH_SERVER_CONFIG"]
logdir = os.environ["LOGSDIR"]

log_files = {
    "file": "file.log",
    "devlog": "devlog.log",
    "hostport": "hostport.log"
}

log_msgs = {
    "file": "logger_type=file in file file.log",
    "devlog": "logger_type=devlog in file devlog.log",
    "hostport": "logger_type=hostport in file hostport.log"
}


def mock_the_handler(logger, logger_type, fname):

    # Assumption: only one Handler is present.
    hdlr = logger.logger.handlers[0]
    logger.logger.removeHandler(hdlr)

    # logger.logger is used: the first logger is used to format 
    # the logs with the help of _styleAdapter and the second is 
    # used to log the messages
    fh = logging.FileHandler(os.path.join(logdir, fname))
    fh.setLevel(logging.DEBUG)
    logger.logger.addHandler(fh)

    return logger


def test_pbench_logger():

    config = PbenchConfig(cfg_name)
    logger = get_pbench_logger(_NAME_, config)

    logger_type = config.get("logging", "logger_type")

    logger = mock_the_handler(logger, logger_type, log_files[logger_type])
    logger.debug(log_msgs[logger_type])

    if os.path.isfile(os.path.join(logdir, log_files[logger_type])):
        with open(os.path.join(logdir, log_files[logger_type]), 'r') as f:
            assert f.read()[:-1] == log_msgs[logger_type], "Mismatch: the file did not contain the expected message."


if __name__ == "__main__":
    try:
        test_pbench_logger()
    except BadConfig as bd:
        print("BadConfig exception was raised")
        sys.exit(1)
