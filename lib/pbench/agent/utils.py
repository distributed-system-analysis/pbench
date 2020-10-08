import logging
import os


def setup_logging(debug, logfile):
    """Setup logging for client
    :param debug: Turn on debug logging
    :param logfile: Logfile to write to
    """
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(message)s"

    rootLogger = logging.getLogger()
    # cause all messages to be processed when the logger is the root logger
    # or delegation to the parent when the logger is a non-root logger
    # see https://docs.python.org/3/library/logging.html
    rootLogger.setLevel(logging.NOTSET)

    streamhandler = logging.StreamHandler()
    streamhandler.setLevel(level)
    streamhandler.setFormatter(logging.Formatter(fmt))
    rootLogger.addHandler(streamhandler)

    if logfile:
        if not os.environ.get("_PBENCH_UNIT_TESTS"):
            fmt = "[%(levelname)-1s][%(asctime)s.%(msecs)d] %(message)s"
        else:
            fmt = "[%(levelname)-1s][1900-01-01T00:00:00.000000] %(message)s"
        filehandler = logging.FileHandler(logfile)
        filehandler.setLevel(logging.NOTSET)
        filehandler.setFormatter(logging.Formatter(fmt))
        rootLogger.addHandler(filehandler)
