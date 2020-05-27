import errno
import grp
import os
import pwd
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


def copyfile(src, dest, perms=None, owner=None):
    """Provide a safe wrapper for a given path, ownership and permissions"""
    try:
        shutil.copyfile(src, dest)
        if owner:
            user, group = owner
            os.chown(dest, pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid)
        if perms:
            os.chmod(dest, perms)
    except shutil.Error:
        raise
    except shutil.SameFileError:
        logger.error("%s and %s are the same file, doing nothing", src, dest)
    except OSError as err:
        if err.errno == errno.ENOENT:
            # Ignore the exception if the path doesnt exist
            pass
        else:
            raise
