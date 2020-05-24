import os
import shutil

from pbench.agent.logger import logger
from pbench.agent.utils import stringify_path


def removetree(path, verbose=False):
    """Remove a directory tree safely given a path"""
    result = 1
    path = stringify_path(path)
    try:
        for p in path.glob("*"):
            if verbose:
                print("Removing %s" % p)
            if p.is_dir():
                removedir(p)
            if p.is_file():
                removefile(p)
        result = 0
    except Exception as ex:
        logger.error("Failed to remove %s: %s", path, ex)

    return result


def removedir(path):
    """Remove a directory safely given a path"""
    shutil.rmtree(stringify_path(path))


def removefile(path):
    """Remove a file safely given a path"""
    os.unlink(stringify_path(path))
