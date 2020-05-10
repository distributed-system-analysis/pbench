import sys

from pbench.lib.agent import logger


def sysexit(code=1):
    """Perform a system exit with a given code, default=1"""
    sys.exit(code)


def sysexit_with_message(msg, code=1):
    """Exit with an error message"""
    logger.error(msg)
    sysexit(code)
