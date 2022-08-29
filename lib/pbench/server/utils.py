import datetime
from logging import Logger
from pathlib import Path
import sys
from typing import List, Union

from dateutil import parser as date_parser

from pbench.common.utils import md5sum
from pbench.server.database.models.datasets import Dataset, DatasetNotFound, Metadata

from . import JSONVALUE


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


def quarantine(error: str, logger: Logger, *files: str):
    """Mark problematic tarballs.

    Add an error status to the Dataset using the metadata subnamespace
    "server.errors" with a key of "quarantine": e.g.,

    "server": {
        "errors": {
            "quarantine": "can't read tarball MD5 file"
        }
    }

    Errors here are fatal but we log an error message to help diagnose
    problems.
    """

    for afile in files:
        try:
            # If the file we're moving is a tarball, update the dataset.
            # If it's the associated MD5 file, skip that.
            if Dataset.is_tarball(afile):
                id = get_tarball_md5(afile)
                try:
                    dataset = Dataset.query(resource_id=id)

                    # "Update" the 'server.errors' key to a potential list of
                    # quarantine errors. We don't have an atomic update at this
                    # time so it's best-effort.
                    #
                    # FIX-ME: I had the idea of support multiple quarantine
                    # reasons, but is that really meaningful vs just directly
                    # updating `server.errors.quarantine` as a string?
                    errors: JSONVALUE = Metadata.getvalue(dataset, "server.errors")
                    if errors:
                        quarantine: List[str] = errors.get("quarantine", [])
                        quarantine.append(error)
                        errors["quarantine"] = quarantine
                    else:
                        errors = {"quarantine": [error]}
                    Metadata.setvalue(dataset, "server.errors", errors)
                except DatasetNotFound:
                    logger.debug("quarantine dataset {} not found", afile)
        except Exception:
            logger.exception("quarantine {!r} {!r} failed", afile, error)
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
