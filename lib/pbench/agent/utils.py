import logging
import pathlib

import numpy as np
import six
from py._path.local import LocalPath

from pbench.agent.logger import logger


def init_wrapper():
    if six.PY2:
        logger.error("Python3 is not installed")

    logging.getLogger("sh").setLevel(logging.WARNING)


def stringify_path(filepath):
    if isinstance(filepath, LocalPath):
        return filepath.strpath
    if isinstance(filepath, str):
        return pathlib.Path(filepath)
    return filepath


def calculate_stddev(values=None):
    values = list(values)
    avg = np.average(values)
    stddev = np.std(values)
    stddevpct = 100 * stddev / avg

    values = np.array(values)
    closest_index = np.abs(values - avg).argmin() + 1

    return (avg, stddev, stddevpct, closest_index)
