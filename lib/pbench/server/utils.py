import datetime
import os
from pathlib import Path
import shutil
import sys
from typing import Union

from dateutil import parser as date_parser

from pbench.common.utils import md5sum
from pbench.server.database.models.datasets import Dataset, States, DatasetNotFound


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


def filesize_bytes(size):
    size = size.strip()
    size_name = ["B", "KB", "MB", "GB", "TB"]
    try:
        parts = size.split(" ", 1)
        if len(parts) == 1:
            try:
                num = int(size)
            except ValueError:
                for i, c in enumerate(size):
                    if not c.isdigit():
                        break
                num = int(size[:i])
                unit = size[i:]
            else:
                unit = ""
        else:
            num = int(parts[0])
            unit = parts[1].strip()

        idx = size_name.index(unit.upper()) if unit else 0
        factor = 1024**idx
    except Exception as exc:
        raise Exception("Invalid file size value encountered, '%s': %s", size, exc)
    else:
        return num * factor


def get_tarball_md5(tarball: Union[Path, str]) -> str:
    """
    Convenience method to locate the MD5 file associated with a dataset
    tarball and read the embedded MD5 hash.

    If the MD5 file isn't present, hash the tarball to compute the MD5. NOTE:
    this shouldn't ever be necessary as a successful upload PUT will always
    result in an MD5 file. This fallback covers several legacy testing cases
    that are otherwise problematic.

    Args:
        tarball: Path or string filepath to a tarball file
    """
    md5_file = Path(f"{str(tarball)}.md5")
    if md5_file.is_file():
        return md5_file.read_text().split()[0]
    return md5sum(tarball).md5_hash


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
            # If the file we're moving is a tarball, update the dataset
            # state. (If it's the associated MD5 file, skip that.)
            if Dataset.is_tarball(afile):
                id = get_tarball_md5(afile)
                try:
                    Dataset.attach(resource_id=id, state=States.QUARANTINED)
                except DatasetNotFound:
                    logger.exception("quarantine dataset {} not found", afile)
            shutil.move(afile, os.path.join(dest, os.path.basename(afile)))
        except Exception:
            logger.exception(
                'quarantine {} {!r}: "mv {} {}/" failed', dest, files, afile, dest
            )
            sys.exit(102)


class UtcTimeHelper:
    """
    A helper class to work with UTC "aware" datetime objects. A "naive" object
    (without timezone offset) will be set to UTC timezone.
    """

    def __init__(self, time: datetime.datetime):
        """
        Capture a datetime object: if it's "naive", set it to be UTC; if
        it's already "aware", adjust it to UTC.

        Args:
            time:   An aware or naive datetime object
        """
        self.utc_time = time
        if self.utc_time.utcoffset() is None:  # naive
            self.utc_time = self.utc_time.replace(tzinfo=datetime.timezone.utc)
        elif self.utc_time.utcoffset():  # Not UTC
            self.utc_time = self.utc_time.astimezone(datetime.timezone.utc)

    @classmethod
    def from_string(cls, time: str) -> "UtcTimeHelper":
        """
        Alternate constructor to build an object by parsing a date-time string.

        Args:
            time:   Standard parseable date-time string

        Returns:
            UtcTimeHelper object
        """
        return cls(date_parser.parse(time))

    def to_iso_string(self) -> str:
        """
        Return an ISO 8601 standard date/time string.
        """
        return self.utc_time.isoformat()

    def __str__(self) -> str:
        """
        Define str() to return the standard ISO time string
        """
        return self.to_iso_string()
