import logging

import six

from pbench.agent.logger import logger


def init_wrapper(self):
    if six.PY2:
        logger.error("Python3 is not installed")

    logging.getLogger("sh").setLevel(logging.WARNING)
