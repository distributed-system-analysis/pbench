from datetime import datetime, tzinfo, timedelta
import os
import shutil
import sys
from time import time as _time


class simple_utc(tzinfo):
    def tzname(self, *args, **kwargs):
        return "UTC"

    def utcoffset(self, dt):
        return timedelta(0)

    def dst(self, dt):
        return timedelta(0)


def tstos(ts=None):
    if ts is None:
        ts = _time()
    dt = datetime.utcfromtimestamp(ts).replace(tzinfo=simple_utc())
    return dt.strftime("%Y-%m-%dT%H:%M:%S-%Z")


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
