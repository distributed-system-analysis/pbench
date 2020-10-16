"""
Utility functions common to both agent and server.
"""
import hashlib

from functools import partial


def md5sum(filename):
    """
    md5sum - return the MD5 check-sum of a given file without reading the
             entire file into memory.

    Returns hex digest string of the given file.
    """
    with open(filename, mode="rb") as f:
        d = hashlib.md5()
        for buf in iter(partial(f.read, 2 ** 20), b""):
            d.update(buf)
    return d.hexdigest()
