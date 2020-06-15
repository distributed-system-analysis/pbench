import os
from pathlib import Path
import shutil

from pbench.agent.logger import logger


def rmtree(d, verbose=False):
    """Remove all files and directories

    :param d: a directory to be removed
    """
    errors = list()

    logger.info("Removing %s", d)
    path = Path(d)
    if path.exists():
        for p in path.glob("*"):
            if verbose:
                logger.info("Removing %s", p)
            if p.is_dir():
                errors = rmdir(p, errors)
            if p.is_file():
                errors = rm(p, errors)
        if len(errors) != 0:
            return (False, errors)
        else:
            return (True, "")


def rmdir(d, errors):
    """Wrapper to remove a given directory

    :param d: A pathlib directory object to remove
    :param errors: an empty list so we can keep track of errors
    """
    try:
        shutil.rmtree(d)
    except Exception as ex:
        errors.append("Failed to remove directory %s: %s", d, ex)
    return errors


def rm(d, errors):
    """Wrapper to remove a file

    :param d: A pathlib file object to remove
    :param errors: an empty list so we can keep track of errors
    """
    try:
        os.unlink(d)
    except Exception as ex:
        errors.append("Failed to remove file %s: %s", d, ex)
    return errors
