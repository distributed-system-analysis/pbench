import logging
import pathlib

import six
from py._path.local import LocalPath

from pbench.agent.logger import logger


def init_wrapper(self):
    if six.PY2:
        logger.error("Python3 is not installed")

    logging.getLogger("sh").setLevel(logging.WARNING)


def stringify_path(filepath):
    if isinstance(filepath, LocalPath):
        return filepath.strpath
    if isinstance(filepath, str):
        return pathlib.Path(filepath)
    return filepath
