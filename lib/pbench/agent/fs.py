import errno
import os
import shutil


def safe_rmtree(directory):
    """Delete a directory, if it's present otherwise no-op"""
    if os.path.exists(directory):
        shutil.rmtree(directory)


def safe_mkdir(directory, clean=False):
    """Safely create a directory.
    Ensures a directory is present.  If it's not there, it is created.  If it is, it's a no-op. If
    clean is True, ensures the directory is empty.
    """
    if clean:
        safe_rmtree(directory)
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
