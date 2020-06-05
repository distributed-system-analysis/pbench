from functools import partial
import hashlib
import os
import sys
import shutil


def rename_tb_link(tb, dest, logger):
    try:
        os.mkdir(dest)
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        logger.exception(
            "os.mkdir: Unable to create tar ball destination directory: {}".format(dest)
        )
        raise
    tbname = os.path.basename(tb)
    tbnewname = os.path.join(dest, tbname)
    try:
        os.rename(tb, tbnewname)
    except Exception:
        logger.exception(
            "os.rename: Unable to move tar ball link {} to destination directory: {}".format(
                tb, dest
            )
        )
        raise


def md5sum(filename):
    """
    Return the MD5 check-sum of a given file.
    We don't want to read the entire file into memory.
    """
    with open(filename, mode="rb") as f:
        d = hashlib.md5()
        for buf in iter(partial(f.read, 128), b""):
            d.update(buf)
    return d.hexdigest()


def quarantine(dest, logger, *files):
    """Quarantine problematic tarballs.
    Errors here are fatal but we log an error message to help diagnose
    problems.
    """
    try:
        os.mkdir(dest)
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        logger.exception('quarantine {} {!r}: "mkdir -p {}/" failed', dest, files, dest)
        sys.exit(101)

    for afile in files:
        if not os.path.exists(afile) and not os.path.islink(afile):
            continue
        try:
            shutil.move(afile, os.path.join(dest, os.path.basename(afile)))
        except Exception:
            logger.exception(
                'quarantine {} {!r}: "mv {} {}/" failed', dest, files, afile, dest
            )
            sys.exit(102)
