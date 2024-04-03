from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum
import errno
import fcntl
from logging import Logger
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from typing import Any, IO, Optional, Union

import humanize
from sqlalchemy import and_

from pbench.common import MetadataLog, selinux
from pbench.server import JSONOBJECT, OperationCode, PathLike, PbenchServerConfig
from pbench.server.database.database import Database
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType
from pbench.server.database.models.datasets import Dataset, DatasetNotFound, Metadata
from pbench.server.utils import get_tarball_md5

RECLAIM_BYTES_PAD = 1024  # Pad unpack reclaim requests by this much
MB_BYTES = 1024 * 1024  # Bytes in Mb
MAX_ERROR = 1024 * 5  # Maximum length of subprocess stderr to capture
TRUNC_PREFIX = "[TRUNC]"  # Indicate that subprocess stderr was truncated


class CacheManagerError(Exception):
    """Base class for exceptions raised from this module."""

    pass


class BadDirpath(CacheManagerError):
    """A bad directory path was given."""

    def __init__(self, error_msg: str):
        super().__init__(error_msg)
        self.error_msg = error_msg


class BadFilename(CacheManagerError):
    """A bad tarball path was given."""

    def __init__(self, path: PathLike):
        super().__init__(f"The file path {path} is not a tarball")
        self.path = str(path)


class CacheExtractBadPath(CacheManagerError):
    """Request to extract a path that's bad or not a file"""

    def __init__(self, tar_name: Path, path: PathLike):
        super().__init__(f"Unable to extract {path} from {tar_name.name}")
        self.name = tar_name.name
        self.path = str(path)


class CacheExtractError(CacheManagerError):
    """Unable to read a cached file"""

    def __init__(self, dataset: str, target: str):
        super().__init__(f"Unable to read {target!r} from {dataset}")
        self.dataset = dataset
        self.target = target


class TarballNotFound(CacheManagerError):
    """The dataset was not found in the ARCHIVE tree."""

    def __init__(self, tarball: str):
        super().__init__(f"The dataset tarball named {tarball!r} is not found")
        self.tarball = tarball


class DuplicateTarball(CacheManagerError):
    """A duplicate tarball name was detected."""

    def __init__(self, tarball: str):
        super().__init__(f"A dataset tarball named {tarball!r} is already present")
        self.tarball = tarball


class MetadataError(CacheManagerError):
    """A problem was found processing a tarball's metadata.log file."""

    def __init__(self, tarball: Path, error: Exception):
        super().__init__(
            f"A problem occurred processing metadata.log from {tarball}: {str(error)!r}"
        )
        self.tarball = tarball
        self.error = str(error)


class UnpackBaseError(CacheManagerError):
    """Base class for unpacking errors"""

    def __init__(self, context: Path, error: str, stderr: Optional[str] = None):
        m = f"{error}: {stderr!r}" if stderr else error
        super().__init__(m)
        self.stderr = stderr


class TarballUnpackError(UnpackBaseError):
    """An error occurred trying to unpack a tarball."""

    def __init__(self, tarball: Path, error: str, stderr: Optional[str] = None):
        super().__init__(
            tarball, f"An error occurred while unpacking {tarball}: {error}", stderr
        )
        self.tarball = tarball


class TarballModeChangeError(UnpackBaseError):
    """An error occurred trying to fix unpacked tarball permissions."""

    def __init__(self, directory: Path, error: str, stderr: Optional[str] = None):
        super().__init__(
            directory,
            f"An error occurred while changing file permissions of {directory}: {error}",
            stderr,
        )
        self.directory = directory


class CacheType(Enum):
    """The type of a file or symlink destination"""

    BROKEN = auto()  # An invalid symlink (absolute or outside tarball)
    DIRECTORY = auto()  # A directory
    FILE = auto()  # A regular file
    OTHER = auto()  # An unsupported file type (mount point, etc.)
    SYMLINK = auto()  # A symbolic link


@dataclass
class CacheObject:
    """Define CacheObject object with file/Directory info attributes.

    Args:
        name: name of File/Directory
        location: path of File/Directory from root Directory
        resolve_path: path of File/Directory after resolution
        resolve_type: type of File/Directory after resolution
        size: size of the File
        type: type of the File/Directory/Symlink
    """

    name: str
    location: Path
    resolve_path: Optional[Path]
    resolve_type: Optional[CacheType]
    size: Optional[int]
    type: CacheType

    @classmethod
    def create(cls, root: Path, path: Path) -> "CacheObject":
        """Collects the file info

        Args:
            root: root directory of cache
            path: path to a file/directory within cache

        Returns:
            CacheObject with file/directory info
        """
        resolve_path: Optional[Path] = None
        resolve_type: Optional[CacheType] = None
        size: Optional[int] = None

        if path.is_symlink():
            ftype = CacheType.SYMLINK
            link_path = path.readlink()
            try:
                if link_path.is_absolute():
                    raise ValueError("symlink target can't be absolute")
                r_path = path.resolve(strict=True)
                resolve_path = r_path.relative_to(root)
            except (FileNotFoundError, ValueError):
                resolve_path = link_path
                resolve_type = CacheType.BROKEN
            else:
                if r_path.is_dir():
                    resolve_type = CacheType.DIRECTORY
                elif r_path.is_file():
                    resolve_type = CacheType.FILE
                else:
                    resolve_type = CacheType.OTHER
        elif path.is_file():
            ftype = CacheType.FILE
            size = path.stat().st_size
        elif path.is_dir():
            ftype = CacheType.DIRECTORY
        else:
            ftype = CacheType.OTHER

        return cls(
            name="" if path == root else path.name,
            location=path.relative_to(root),
            resolve_path=resolve_path,
            resolve_type=resolve_type,
            size=size,
            type=ftype,
        )


# Type hint definitions for the cache map.
#
# CacheMapEntry: { "details": CacheObject, "children": CacheMap }
# CacheMap: { "<directory_entry>": CacheMapEntry, ... }
CacheMapEntry = dict[str, Union[CacheObject, "CacheMap"]]
CacheMap = dict[str, CacheMapEntry]


class LockRef:
    """Keep track of a cache lock passed off to a caller"""

    def __init__(self, lock: Path):
        """Initialize a lock reference

        The lock file is opened in "w+" mode, which is "write update": unlike
        "r+", this creates the file if it doesn't already exist, but still
        allows lock conversion between LOCK_EX and LOCK_SH.

        Args:
            lock: the path of a lock file
        """
        self.lock = lock.open("w+")
        self.locked = False
        self.exclusive = False

    def acquire(self, exclusive: bool = False, wait: bool = True) -> "LockRef":
        """Acquire the lock

        Args:
            exclusive: lock for exclusive access
            wait: wait for lock

        Raises:
            OSError (EAGAIN or EACCES): wait=False and the lock is already
                owned

        Returns:
            The lockref, so this can be chained with the constructor
        """

        self.exclusive = exclusive
        cmd = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        if not wait:
            cmd |= fcntl.LOCK_NB
        fcntl.lockf(self.lock, cmd)
        self.locked = True
        return self

    def release(self):
        """Release the lock and close the lock file"""

        if not self.locked:
            return
        try:
            fcntl.lockf(self.lock, fcntl.LOCK_UN)
            self.lock.close()
        finally:
            # Release our reference to the lock file so that the
            # object can be reclaimed.
            self.locked = False
            self.exclusive = False
            self.lock = None

    def upgrade(self):
        """Upgrade a shared lock to exclusive"""
        if not self.exclusive:
            fcntl.lockf(self.lock, fcntl.LOCK_EX)
            self.exclusive = True

    def downgrade(self):
        """Downgrade an exclusive lock to shared"""
        if self.exclusive:
            fcntl.lockf(self.lock, fcntl.LOCK_SH)
            self.exclusive = False


class LockManager:
    def __init__(self, lock: Path, exclusive: bool = False, wait: bool = True):
        self.lock = LockRef(lock)
        self.exclusive = exclusive
        self.wait = wait
        self.unlock = True

    def keep(self) -> "LockManager":
        """Tell the context manager not to unlock on exit"""
        self.unlock = False
        return self

    def release(self):
        """Release manually if necessary"""
        self.lock.release()

    def upgrade(self):
        """Upgrade a shared lock to exclusive"""
        self.lock.upgrade()
        self.exclusive = True

    def downgrade(self):
        """Downgrade an exclusive lock to shared"""
        self.lock.downgrade()
        self.exclusive = False

    def __enter__(self) -> "LockManager":
        """Enter a lock context manager by acquiring the lock

        Raises:
            OSError: self.wait is False, and the lock is already owned.

        Returns:
            the LockManager object
        """
        self.lock.acquire(exclusive=self.exclusive, wait=self.wait)
        return self

    def __exit__(self, *exc):
        """Exit a lock context manager by releasing the lock

        This does nothing if "unlock" has been cleared, meaning we want the
        lock to persist beyond the context manager scope.
        """
        if self.unlock:
            self.lock.release()


class Inventory:
    """Encapsulate the file stream and cache lock management

    This encapsulation allows cleaner downstream handling, so that we can close
    both the extracted file stream and unlock the dataset cache after the file
    reference is complete. In APIs the Inventory close is done by the Flask
    infrastructure after the response handling is done.
    """

    def __init__(
        self,
        stream: IO[bytes],
        lock: Optional[LockRef] = None,
        subproc: Optional[subprocess.Popen] = None,
    ):
        """Construct an instance to track extracted inventory

        This encapsulates many byte stream operations so that it can be used
        as if it were a byte stream.

        Args:
            stream: the data stream of a specific tarball member
            lock: a cache lock reference
            subproc: a Popen object to clean up on close
        """
        self.stream = stream
        self.lock = lock
        self.subproc = subproc

    def close(self):
        """Close the byte stream and clean up the Popen object"""

        exception = None
        if self.subproc:
            try:
                if self.subproc.poll() is None:
                    # The subprocess is still running: kill it, drain the outputs,
                    # and wait for its termination.  (If the timeout on the wait()
                    # is exceeded, it will raise subprocess.TimeoutExpired rather
                    # than waiting forever...it's not clear what will happen after
                    # that, but there's not a good alternative, so I hope this
                    # never actually happens.)
                    self.subproc.kill()
                    if self.subproc.stdout:
                        while self.subproc.stdout.read(4096):
                            pass
                    if self.subproc.stderr:
                        while self.subproc.stderr.read(4096):
                            pass
                    self.subproc.wait(60.0)
            except Exception as e:
                # Release our reference to the subprocess.Popen object so that the
                # object can be reclaimed.
                self.subproc = None
                exception = e
        if self.lock:
            try:
                self.lock.release()
            except Exception as e:
                exception = e
        self.stream.close()

        # NOTE: if both subprocess cleanup and unlock fail with exceptions, we
        # raise the latter, and the former will be ignored. In practice, that's
        # not a problem as we only construct an Inventory with a subprocess
        # reference for extract, which doesn't need to lock a cache directory.
        if exception:
            raise exception

    def getbuffer(self):
        """Return the underlying byte buffer (used by send_file)"""
        return self.stream.getbuffer()

    def read(self, *args, **kwargs) -> bytes:
        """Encapsulate a read operation"""
        return self.stream.read(*args, **kwargs)

    def readable(self) -> bool:
        """Return the readable state of the stream"""
        return self.stream.readable()

    def seek(self, *args, **kwargs) -> int:
        """Allow setting the relative position in the stream"""
        return self.stream.seek(*args, **kwargs)

    def __repr__(self) -> str:
        """Return a string representation"""
        return f"<Stream {self.stream} from {self.lock.name if self.lock else self.subproc if self.subproc else None}>"

    def __iter__(self):
        """Allow iterating through lines in the buffer"""
        return self

    def __next__(self):
        """Iterate through lines in the buffer"""
        line = self.stream.readline()
        if line:
            return line
        else:
            raise StopIteration()


class Tarball:
    """Representation of an on-disk tarball.

    This class corresponds to the physical representation of a Dataset: the
    tarball, the MD5 file, and unpacked (cached) data.

    It provides discovery and management methods related to a specific
    dataset's on-disk representation. This class does not interact with the
    database representations of a dataset.
    """

    # Wait no more than a minute for the tar(1) command to start producing
    # output; perform the wait in 0.02s increments.
    TAR_EXEC_TIMEOUT = 60.0
    TAR_EXEC_WAIT = 0.02

    def __init__(self, path: Path, resource_id: str, controller: "Controller"):
        """Construct a `Tarball` object instance

        Args:
            path: The file path to a discovered tarball (.tar.xz file) in the
                configured ARCHIVE directory for a controller.
            resource_id: The dataset resource ID
            controller: The associated Controller object
        """
        self.logger: Logger = controller.logger

        # Record the root filename of the tarball
        self.name: str = Dataset.stem(path)

        # Record the Dataset resource ID (MD5) for coordination with the server
        # logic
        self.resource_id: str = resource_id

        # Record the Dataset record
        try:
            dataset = Dataset.query(resource_id=resource_id)
            self.dataset = dataset
        except DatasetNotFound:
            self.dataset = None

        # Record a backlink to the containing controller object
        self.controller: Controller = controller

        # Record the tarball isolation directory
        self.isolator = controller.path / resource_id

        # Record the path of the tarball file
        self.tarball_path: Path = path

        # Record the path of the companion MD5 file
        self.md5_path: Path = path.with_suffix(".xz.md5")

        # Record where cached unpacked data would live
        self.cache: Path = controller.cache / self.resource_id

        # We need the directory to lock, so make sure it's there
        self.cache.mkdir(parents=True, exist_ok=True)

        # Record hierarchy of a Tar ball
        self.cachemap: Optional[CacheMapEntry] = None

        # Record the base of the unpacked files for cache management, which
        # is (self.cache / self.name) and will be None when the cache is
        # inactive.
        self.unpacked: Optional[Path] = None

        # Record the unpacked dataset size.
        self.unpacked_size: Optional[int] = None

        # Record the lockf file path used to control cache access
        self.lock: Path = self.cache / "lock"

        # Record a marker file path used to record the last cache access
        # timestamp
        self.last_ref: Path = self.cache / "last_ref"

        # Record the path of the companion MD5 file
        self.md5_path: Path = path.with_suffix(".xz.md5")

        # Record the name of the containing controller
        self.controller_name: str = controller.name

        # Cache results metadata when it's been processed
        self.metadata: Optional[JSONOBJECT] = None

    def check_unpacked(self):
        """Determine whether a tarball has been unpacked.

        Look for the unpacked data root, and record it if found.
        """
        unpack = self.cache / self.name
        if unpack.is_dir():
            self.unpacked = unpack

    # Most of the "operational" methods below this point should be called only
    # through Controller and/or CacheManager methods, in order to properly manage
    # aspects of the cache manager structure outside the scope of the Tarball.
    #
    # create
    #   Alternate constructor to create a Tarball object and move an incoming
    #   tarball and md5 into the proper controller directory.
    #
    # unpack
    #   Unpack the ARCHIVE tarball file into a new directory under the
    #   CACHE directory tree.
    #
    # uncache
    #   Remove the unpacked directory tree under CACHE when no longer needed.
    #
    # delete
    #   Remove the tarball and MD5 file from ARCHIVE after uncaching the
    #   unpacked directory tree.

    @classmethod
    def create(
        cls, tarball: Path, resource_id: str, controller: "Controller"
    ) -> "Tarball":
        """An alternate constructor to import a tarball

        This moves a new tarball into the proper place along with the md5
        companion file. It returns the new Tarball object.

        Args:
            tarball: location of the tarball
            resource_id: tarball resource ID
            controller: associated controller object

        Returns:
            Tarball object
        """

        # Validate the tarball suffix and extract the dataset name
        name = Dataset.stem(tarball)

        # NOTE: with_suffix replaces only the final suffix, .xz, not the full
        # standard .tar.xz
        md5_source = tarball.with_suffix(".xz.md5")

        # It's possible that two similar benchmark runs at about the same
        # time can result in identical filenames with distinct MD5 values
        # (for example, the same basic benchmark run on two hosts, which
        # has been observed in automated cloud testing). To avoid problems, we
        # "isolate" each tarball and its MD5 companion in a subdirectory with
        # the md5 (resource_id) string to prevent collisions. The Tarball
        # object maintains this, but we need it here, first, to move the
        # files.
        isolator = controller.path / resource_id

        # NOTE: we enable "parents" and "exist_ok" not because we expect these
        # conditions (both should be impossible) but because it's not worth an
        # extra error check. We'll fail below if either *file* already
        # exists in the isolator directory.
        isolator.mkdir(parents=True, exist_ok=True)
        destination = isolator / tarball.name
        md5_destination = isolator / md5_source.name

        # If either expected destination file exists, something is wrong
        if destination.exists() or md5_destination.exists():
            raise DuplicateTarball(name)

        # Move the MD5 file first; only if that succeeds, move the tarball
        # itself. Note that we expect the source to be on the same
        # filesystem as the ARCHIVE tree, and we want to avoid using double
        # the space by copying large tarballs if the file can be moved.
        try:
            shutil.move(md5_source, md5_destination)
        except Exception as e:
            md5_destination.unlink(missing_ok=True)
            controller.logger.error(
                "ERROR moving dataset {} ({}) MD5: {}", name, tarball, e
            )
            raise

        try:
            shutil.move(tarball, destination)
        except Exception as e:
            try:
                md5_destination.unlink(missing_ok=True)
            except Exception as md5_e:
                controller.logger.error(
                    "Unable to recover by removing {} MD5 after tarball copy failure: {}",
                    name,
                    md5_e,
                )
            destination.unlink(missing_ok=True)
            controller.logger.error(
                "ERROR moving dataset {} tarball {}: {}", name, tarball, e
            )
            raise

        # Restore the SELinux context properly
        try:
            if selinux.is_selinux_enabled():
                selinux.restorecon(destination)
                selinux.restorecon(md5_destination)
        except Exception as e:
            # log it but do not abort
            controller.logger.error("Unable to set SELINUX context for {}: {}", name, e)

        # If we were able to copy both files, remove the originals. If we moved
        # the files above, instead of copying them, these will no longer exist
        # and we'll ignore that condition silently.
        try:
            tarball.unlink(missing_ok=True)
        except Exception as e:
            controller.logger.error("Error removing staged tarball {}: {}", name, e)
        try:
            md5_source.unlink(missing_ok=True)
        except Exception as e:
            controller.logger.error("Error removing staged MD5 {}: {}", name, e)

        return cls(destination, resource_id, controller)

    def build_map(self):
        """Build hierarchical representation of results tree

        This must be called with the cache locked (shared lock is enough)
        and unpacked.

        NOTE: this structure isn't removed when we release the cache, as the
        data remains valid so long as the dataset exists.
        """
        cmap: CacheMapEntry = {
            "details": CacheObject.create(self.unpacked, self.unpacked)
        }
        dir_queue = deque(((self.unpacked, cmap),))
        while dir_queue:
            unpacked, parent_map = dir_queue.popleft()
            curr: CacheMap = {}
            for path in unpacked.glob("*"):
                details = CacheObject.create(self.unpacked, path)
                curr[path.name] = {"details": details}
                if path.is_dir() and not path.is_symlink():
                    dir_queue.append((path, curr[path.name]))
            parent_map["children"] = curr

        self.cachemap = cmap

    def find_entry(self, path: Path) -> CacheMapEntry:
        """Locate a node in the cache map

        Args:
            path: relative path of the subdirectory/file

        Raises:
            BadDirpath if the directory/file path is not valid or doesn't
                correspond to an entity within the tarball.

        Returns:
            cache map entry
        """
        if str(path).startswith("/"):
            raise BadDirpath(
                f"The path {str(path)!r} is an absolute path,"
                " we expect relative path to the root directory."
            )

        if not self.cachemap:
            with LockManager(self.lock) as lock:
                self.get_results(lock)

        if str(path) == ".":
            return self.cachemap

        path_parts = path.parts[:-1]
        node: CacheMap = self.cachemap["children"]

        try:
            for dir in path_parts:
                info: CacheMapEntry = node[dir]
                if info["details"].type is CacheType.DIRECTORY:
                    node = info["children"]
                else:
                    raise BadDirpath(
                        f"Found a file {dir!r} where a directory was expected in path {str(path)!r}"
                    )
            return node[path.name]
        except KeyError as exc:
            raise BadDirpath(
                f"Can't resolve path {str(path)!r}: component {exc} is missing."
            )

    @staticmethod
    def extract(tarball_path: Path, path: str) -> Inventory:
        """Returns a file stream for a file within a tarball

        NOTE: This should generally be used only within the INTAKE path before
        it's practical to load the cache with a fully unpacked tree. The
        extracted file is not cached and therefore each reference will repeat
        the tar file extraction.

        Args:
            tarball_path: absolute path of the tarball
            path: relative path within the tarball

        Returns:
            An inventory object that mimics an IO[bytes] object while also
            maintaining a reference to the subprocess.Popen object to be
            cleaned up later.

        Raise:
            CacheExtractBadPath if the target cannot be extracted
            TarballUnpackError on other tar-command failures
            Any exception raised by subprocess.Popen()
            subprocess.TimeoutExpired if the tar command hangs
        """
        tar_path = shutil.which("tar")
        if tar_path is None:
            raise TarballUnpackError(
                tarball_path, "External 'tar' executable not found"
            )

        # The external tar utility offers better capabilities than the
        # Standard Library package, so run it in a subprocess:  extract
        # the target member from the specified tar archive and direct it to
        # stdout; we expect only one occurrence of the target member, so stop
        # processing as soon as we find it instead of looking for additional
        # instances of it later in the archive -- this is a huge savings when
        # the archive is very large.
        tar_command = [
            str(tar_path),
            "xf",
            tarball_path,
            "--to-stdout",
            "--occurrence=1",
            path,
        ]
        tarproc = subprocess.Popen(
            tar_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for the tar(1) command to start producing output, but stop
        # waiting if the subprocess exits or if it takes too long.
        start = time.time()
        while not tarproc.stdout.peek():
            if tarproc.poll() is not None:
                break

            elapsed = time.time() - start
            if elapsed > Tarball.TAR_EXEC_TIMEOUT:
                # No signs of life from the subprocess.  Kill it to ensure that
                # the Python runtime can clean it up after we leave, and report
                # the failure.
                tarproc.kill()
                raise subprocess.TimeoutExpired(
                    cmd=tar_command,
                    timeout=elapsed,
                    output=tarproc.stdout,
                    stderr=tarproc.stderr,
                )

            time.sleep(Tarball.TAR_EXEC_WAIT)

        # If the return code is None (meaning the command is still running) or
        # is zero (meaning it completed successfully), then return the stream
        # containing the extracted file to our caller, and return the Popen
        # object so that we can clean it up when the Inventory object is closed.
        if not tarproc.returncode:
            return Inventory(tarproc.stdout, subproc=tarproc)

        # The tar command was invoked successfully (otherwise, the Popen()
        # constructor would have raised an exception), but it exited with
        # an error code.  We have to glean what went wrong by looking at
        # stderr, which is fragile but the only option.  Rather than
        # relying on looking for specific text, we assume that, if the error
        # references the archive member, then it was a bad path; otherwise, it
        # was some sort of error unpacking it.
        error_text = tarproc.stderr.read().decode()
        if path in error_text:
            # "tar: missing_member.txt: Not found in archive"
            raise CacheExtractBadPath(tarball_path, path)
        # "tar: /path/to/bad_tarball.tar.xz: Cannot open: No such file or directory"
        raise TarballUnpackError(
            tarball_path, f"Unexpected error from {tar_path}: {error_text!r}"
        )

    def get_contents(self, path: str, origin: str) -> JSONOBJECT:
        """Return a description of a directory.

        Args:
            path: relative path within the tarball
            origin: root URI path for the dataset

        Returns:
            A "json" dict describing the target.
        """

        with LockManager(self.lock) as lock:
            artifact: Path = self.get_results(lock) / path
            try:
                # NOTE: os.path.abspath() removes ".." but Path.absolute(),
                # doesn't, meaning the latter allows a query with path "..",
                # and we don't want to allow reaching outside of the tarball.
                arel = Path(os.path.abspath(artifact)).relative_to(self.unpacked)
            except Exception:
                raise CacheExtractError(self.name, path)
            if artifact.is_dir() and not artifact.is_symlink():
                dir_list = []
                file_list = []
                for f in artifact.iterdir():
                    relative = f.relative_to(self.unpacked)
                    if f.is_symlink():
                        append_to = file_list
                        target = f.resolve()
                        try:
                            link = target.relative_to(self.unpacked)
                        except Exception:
                            link = f.readlink()
                            uri = f"{origin}/inventory/{relative}"
                            link_type = CacheType.BROKEN
                        else:
                            if target.is_dir():
                                uri = f"{origin}/contents/{link}"
                                link_type = CacheType.DIRECTORY
                                append_to = dir_list
                            elif target.is_file():
                                uri = f"{origin}/inventory/{link}"
                                link_type = CacheType.FILE
                            else:
                                uri = f"{origin}/inventory/{relative}"
                                link_type = CacheType.OTHER
                        append_to.append(
                            {
                                "name": f.name,
                                "type": CacheType.SYMLINK.name,
                                "link": str(link),
                                "link_type": link_type.name,
                                "uri": uri,
                            }
                        )
                    elif f.is_dir():
                        dir_list.append(
                            {
                                "name": f.name,
                                "type": CacheType.DIRECTORY.name,
                                "uri": f"{origin}/contents/{relative}",
                            }
                        )
                    else:
                        t = CacheType.FILE if f.is_file() else CacheType.OTHER
                        r = {
                            "name": f.name,
                            "type": t.name,
                            "uri": f"{origin}/inventory/{relative}",
                        }
                        if t is CacheType.FILE:
                            r["size"] = f.stat().st_size
                        file_list.append(r)

                # Normalize because we want the "root" directory to be reported as
                # "" rather than as Path's favored "."
                loc = str(arel)
                name = artifact.name
                if loc == ".":
                    loc = ""
                    name = ""
                dir_list.sort(key=lambda d: d["name"])
                file_list.sort(key=lambda d: d["name"])
                val = {
                    "name": name,
                    "type": CacheType.DIRECTORY.name,
                    "directories": dir_list,
                    "files": file_list,
                    "uri": f"{origin}/contents/{loc}",
                }
            else:
                access = "inventory"
                link_type = CacheType.FILE
                ltype = CacheType.OTHER
                if artifact.is_symlink():
                    link_type = CacheType.SYMLINK
                    try:
                        target = artifact.resolve(strict=True)
                        trel = target.relative_to(self.unpacked)
                        if target.is_dir():
                            access = "contents"
                            ltype = CacheType.DIRECTORY
                            arel = trel
                        elif target.is_file():
                            ltype = CacheType.FILE
                            arel = trel
                        else:
                            ltype = CacheType.OTHER
                    except Exception:
                        ltype = CacheType.BROKEN
                        trel = artifact.readlink()
                elif not artifact.is_file():
                    link_type = CacheType.OTHER

                val = {
                    "name": artifact.name,
                    "type": link_type.name,
                    "uri": f"{origin}/{access}/{arel}",
                }
                if link_type is CacheType.SYMLINK:
                    val["link"] = str(trel)
                    val["link_type"] = ltype.name
                if link_type is CacheType.FILE or ltype is CacheType.FILE:
                    val["size"] = artifact.stat().st_size
            return val

    def get_inventory(self, path: str) -> dict[str, Any]:
        """Return a JSON description of a tarball member file.

        If "path" is a directory, release the cache lock and return the path
        and type.

        If "path" is a regular file, the returned data includes an Inventory
        object with a byte stream, and transfers ownership of the cache lock to
        the caller. When done with the file Inventory stream, the caller must
        close the Inventory object to release the file stream and the cache
        lock.

        if "path" is anything else, the cache lock is released and an exception
        is raised.

        Raises:
            CacheExtractBadPath: the path does not match a directory or regular
                file within the tarball.

        Args:
            path: relative path within the tarball of a file

        Returns:
            Dictionary with file info and file stream
        """
        if not path:
            return {
                "name": self.tarball_path.name,
                "type": CacheType.FILE,
                "stream": Inventory(self.tarball_path.open("rb")),
            }
        else:
            with LockManager(self.lock) as lock:
                artifact: Path = self.get_results(lock) / path
                if artifact.is_dir():
                    stream = None
                    type = CacheType.DIRECTORY
                elif artifact.is_file():
                    stream = Inventory(artifact.open("rb"), lock=lock.keep())
                    type = CacheType.FILE
                else:
                    raise CacheExtractBadPath(self.tarball_path, path)
            return {"name": path, "type": type, "stream": stream}

    @staticmethod
    def _get_metadata(tarball_path: Path) -> JSONOBJECT:
        """Fetch the values in metadata.log from the tarball.

        Args:
            tarball_path: a file path to a tarball

        Returns:
            A JSON representation of the dataset `metadata.log`
        """
        name = Dataset.stem(tarball_path)
        data = Tarball.extract(tarball_path, f"{name}/metadata.log")
        metadata_log = MetadataLog()
        metadata_log.read_file(e.decode() for e in data)
        data.close()
        metadata = {s: dict(metadata_log.items(s)) for s in metadata_log.sections()}
        return metadata

    @staticmethod
    def subprocess_run(
        command: str,
        working_dir: PathLike,
        exception: type[UnpackBaseError],
        ctx: Path,
    ):
        """Runs a command as a subprocess.

        Args:
            command: command to be executed.
            working_dir: Directory where tarball needs to be unpacked.
            exception: A reference to a class (e.g., TarballUnpackError or
                        TarballModeChangeError) to be raised in the event of an error.
            ctx: tarball path/unpack directory path. This is only used at
                the event of an error as a parameter to the CacheManagerError Exception.

        Raises:
            In the event of an error, will raise an instance of the class specified
            by the `exception` parameter, instantiated with the value of the
            `ctx` arguments and an explanatory message.
        """
        cmd = shlex.split(command)
        try:
            process = subprocess.run(
                cmd,
                cwd=working_dir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            raise exception(ctx, str(exc)) from exc
        else:
            if process.returncode != 0:
                msg = process.stderr
                if len(msg) > MAX_ERROR - len(TRUNC_PREFIX):
                    msg = (TRUNC_PREFIX + msg)[:MAX_ERROR]
                raise exception(
                    ctx,
                    f"{cmd[0]} exited with status {process.returncode}",
                    stderr=msg,
                )

    def get_unpacked_size(self) -> int:
        """Get the unpacked size of a dataset

        Once we've unpacked it once, the size is tracked in the metadata key
        'server.unpacked'. If we haven't yet unpacked it, and the dataset's
        metadata.log provides "run.raw_size", use that as an estimate (the
        accuracy depends on relative block size compared to the server).

        Returns:
            unpacked size of the tarball, or 0 if unknown
        """
        if self.unpacked_size:
            return self.unpacked_size

        if not self.dataset:
            return 0

        source = Metadata.SERVER_UNPACKED
        size = Metadata.getvalue(self.dataset, source)
        if not size:
            try:
                source = "dataset.metalog.run.raw_size"
                size = int(Metadata.getvalue(self.dataset, source))
            except (ValueError, TypeError):
                source = None
                size = 0
        self.unpacked_size = size
        return size

    def get_results(self, lock: LockManager) -> Path:
        """Unpack a tarball into a temporary directory tree

        Make sure that the dataset results are unpacked into a cache tree. The
        location of the unpacked tree is in self.unpacked and is also returned
        direct to the caller.

        Args:
            lock: A lock context manager in shared lock state

        Returns:
            the root Path of the unpacked directory tree
        """

        if not self.unpacked:
            start = time.time()
            reclaim = start
            lock.upgrade()

            # If necessary, attempt to reclaim some unused cache so we have
            # enough room.
            if self.controller and self.controller.cache_manager:
                self.controller.cache_manager.reclaim_cache(
                    goal_bytes=self.get_unpacked_size() + RECLAIM_BYTES_PAD
                )
                reclaim = time.time()

            audit = None
            error = None
            try:
                audit = Audit.create(
                    name="cache",
                    operation=OperationCode.CREATE,
                    status=AuditStatus.BEGIN,
                    user_name=Audit.BACKGROUND_USER,
                    object_type=AuditType.DATASET,
                    object_id=self.resource_id,
                    object_name=self.name,
                )
            except Exception as e:
                self.controller.logger.warning(
                    "Unable to audit unpack for {}: '{}'", self.name, e
                )

            ustart = time.time()
            try:
                tar_command = "tar -x --no-same-owner --delay-directory-restore "
                tar_command += f"--force-local --file='{str(self.tarball_path)}'"
                self.subprocess_run(
                    tar_command, self.cache, TarballUnpackError, self.tarball_path
                )
                find_command = "find . ( -type d -exec chmod ugo+rx {} + ) -o ( -type f -exec chmod ugo+r {} + )"
                self.subprocess_run(
                    find_command, self.cache, TarballModeChangeError, self.cache
                )
                self.unpacked = self.cache / self.name
            except Exception as e:
                error = str(e)
                raise
            finally:
                if audit:
                    attributes = {"error": error} if error else {}
                    Audit.create(
                        root=audit,
                        status=AuditStatus.FAILURE if error else AuditStatus.SUCCESS,
                        attributes=attributes,
                    )
                lock.downgrade()
            uend = time.time()
            self.logger.info(
                "{}: reclaim {:.3f}, unpack {:.3f}",
                self.name,
                reclaim - start,
                uend - ustart,
            )

            # If we have a Dataset, and haven't already done this, compute the
            # unpacked size and record it in metadata so we can use it later.
            ssize = time.time()
            if self.dataset:
                if not Metadata.getvalue(self.dataset, Metadata.SERVER_UNPACKED):
                    try:
                        process = subprocess.run(
                            ["du", "-s", "-B1", str(self.unpacked)],
                            capture_output=True,
                            text=True,
                        )
                        if process.returncode == 0:
                            size = int(process.stdout.split("\t", maxsplit=1)[0])
                            self.unpacked_size = size
                            Metadata.setvalue(
                                self.dataset, Metadata.SERVER_UNPACKED, size
                            )
                    except Exception as e:
                        self.logger.warning("usage check failed: {}", e)

                # Update the time-to-unpack statistic. If the metadata doesn't exist,
                # or somehow isn't a dict (JSONOBJECT), create a new metric: otherwise
                # update the existing metric.
                unpack_time = uend - ustart
                metric: JSONOBJECT = Metadata.getvalue(
                    self.dataset, Metadata.SERVER_UNPACK_PERF
                )
                if not isinstance(metric, dict):
                    metric = {"min": unpack_time, "max": unpack_time, "count": 1}
                else:
                    # We max out at about 12 days here, which seems safely excessive!
                    metric["min"] = min(metric.get("min", 1000000.0), unpack_time)
                    metric["max"] = max(metric.get("max", 0), unpack_time)
                    metric["count"] = metric.get("count", 0) + 1
                Metadata.setvalue(self.dataset, Metadata.SERVER_UNPACK_PERF, metric)
                self.logger.info(
                    "{}: size update {:.3f}", self.name, time.time() - ssize
                )

        self.last_ref.touch(exist_ok=True)
        return self.unpacked

    def cache_delete(self):
        """Remove the unpacked tarball directory and all contents.

        WARNING:

        This is unprotected!

        Normal cache reclaim is managed using the `tree_manage --reclaim` CLI
        command, generally through the `pbench-reclaim.timer` service, which
        calls this method only when the cache is unlocked and aged out.
        """
        self.cachemap = None
        if self.unpacked:
            try:
                shutil.rmtree(self.unpacked)
                self.unpacked = None
            except Exception as e:
                self.logger.error("cache reclaim for {} failed with {}", self.name, e)
                raise

    def delete(self):
        """Delete the tarball and MD5 file from the ARCHIVE tree.

        We'll log errors in deletion, but "succeed" and clear the links to both
        files. There's nothing more we can do.
        """

        # NOTE: this is similar to cache_delete above, but doesn't re-raise and
        # operates on the root cache directory rather than unpack.
        self.cachemap = None
        if self.cache:
            try:
                shutil.rmtree(self.cache)
            except Exception as e:
                self.logger.error("cache delete for {} failed with {}", self.name, e)

        # Remove the isolator directory with the tarball and MD5 files; or if
        # this is a pre-isolator tarball, unlink the MD5 and tarball.
        if self.isolator and self.isolator.exists():
            try:
                shutil.rmtree(self.isolator)
            except Exception as e:
                self.logger.error("isolator delete for {} failed with {}", self.name, e)
            self.isolator = None
            self.tarball_path = None
            self.md5_path = None
        else:
            if self.md5_path:
                try:
                    self.md5_path.unlink()
                except Exception as e:
                    self.logger.error(
                        "archive unlink for {} failed with {}", self.name, e
                    )
                self.md5_path = None
            if self.tarball_path:
                try:
                    self.tarball_path.unlink()
                except Exception as e:
                    self.logger.error(
                        "archive MD5 unlink for {} failed with {}", self.name, e
                    )
                self.tarball_path = None


class Controller:
    """Record the existence of a "controller" in the ARCHIVE directory tree

    This only means that a directory was found within the root ARCHIVE
    directory. A controller with no data will be ignored in most contexts,
    but the audit report generator will flag it.
    """

    def __init__(self, path: Path, cache: Path, logger: Logger, discover: bool = True):
        """Manage the representation of a controller archive on disk.

        In this context, the path parameter refers to a controller directory
        within the configured ARCHIVE tree. There need not be any files or
        directories related to this controller at this time.

        Args:
            path: Controller ARCHIVE directory path
            cache: The base of the cache tree
            logger: Logger object
            discover: Discover all tarballs if True
        """
        self.logger = logger

        # A link back to the cache manager object
        self.cache_manager: Optional[CacheManager] = None

        # The controller file system (directory) name
        self.name = path.name

        # The full controller path in the ARCHIVE tree
        self.path = path

        # Remember the cache tree base
        self.cache = cache

        # Provide a mapping from Tarball file name to object
        self.tarballs: dict[str, Tarball] = {}

        # Provide a mapping from Dataset resource ID to object
        self.datasets: dict[str, Tarball] = {}

        # Discover the tarballs that already exist.
        # Depends on instance properties and should remain at the end of the
        # constructor!
        if discover:
            self._discover_tarballs()

    def _add_if_tarball(self, file: Path, md5: Optional[str] = None) -> bool:
        """Check for a tar file, and create an object

        Args:
            file: path of potential tarball
            md5: known MD5 hash, or None to compute here

        Returns:
            true if the tarball was added
        """

        if not (file.is_file() and Dataset.is_tarball(file)):
            return False

        hash = md5 if md5 else get_tarball_md5(file)
        tarball = Tarball(file, hash, self)
        self.tarballs[tarball.name] = tarball
        self.datasets[tarball.resource_id] = tarball
        tarball.check_unpacked()
        return True

    def _discover_tarballs(self):
        """Discover the known tarballs

        Look in the ARCHIVE tree's controller directory for tarballs, and add
        them to the known set. "Old" tarballs may be at the top level, "new"
        tarballs are in "resource_id" isolation directories.

        We also check for unpacked directories in the CACHE tree matching the
        resource_id of any tarballs we find in order to link them.
        """
        for file in self.path.iterdir():
            if file.is_dir():
                md5 = file.name
                for tar in file.iterdir():
                    self._add_if_tarball(tar, md5)
            else:
                self._add_if_tarball(file)

    @classmethod
    def create(
        cls, name: str, options: PbenchServerConfig, logger: Logger
    ) -> "Controller":
        """Create a new controller directory under the ARCHIVE tree

        Returns:
            Controller object
        """
        controller_dir = options.ARCHIVE / name
        controller_dir.mkdir(exist_ok=True, mode=0o755)
        return cls(controller_dir, options.CACHE, logger)

    def create_tarball(self, tarfile_path: Path) -> Tarball:
        """Create a new dataset tarball object under the controller

        The new tarball object is linked to the controller so we can find it.

        Args:
            tarfile_path: Path to source tarball file

        Returns:
            Tarball object
        """
        tarball = Tarball.create(tarfile_path, get_tarball_md5(tarfile_path), self)
        self.datasets[tarball.resource_id] = tarball
        self.tarballs[tarball.name] = tarball
        return tarball

    def delete(self, dataset_id: str):
        """Delete a dataset tarball and remove it from the controller

        Args:
            dataset_id: Resource ID of dataset to delete
        """
        tarball = self.datasets[dataset_id]
        name = tarball.name
        tarball.delete()
        del self.datasets[dataset_id]
        del self.tarballs[name]


class CacheManager:
    """A hierarchical representation of the Pbench Server's file structure.

    The cache manager manages two directory trees:

    ARCHIVE

        The ARCHIVE tree is specified by the pbench-archive-dir variable in the
        pbench-server-default.cfg file. The normal value is rooted under the
        designated pbench-top-dir, conventionally something like

            /srv/pbench/archive/fs-version-001/

        A directory is created under this root for each controller name used by
        a dataset. Within each ARCHIVE controller directory you'll find:

            A set of Pbench Agent dataset results, each comprising a ".tar.xz"
            tar archive (conventionally referred to as a "tarball") and a
            ".tar.xz.md5" MD5 file with the same base name.

    CACHE

        The CACHE tree is rooted under the Pbench "top dir" directory,
        with the default path:

            /srv/pbench/.cache/

        This tree will contain temporary directories of unpacked tarballs to
        allow establishing a cache manager map and for indexing (which requires
        a fully unpacked tarball tree for efficiency). After indexing, these
        directories are deleted, but the cache manager may dynamically unpack
        files or subtrees here during normal operation.
    """

    # The CacheManager class provides a definition of a directory at the same level
    # as "controller" directories, where `PUT` will temporarily store uploaded
    # tarballs and generated MD5 files.
    #
    # Placing this within the ARCHIVE tree ensures that we can rename files to
    # a controller directory instead of copying them, and the upload will
    # already fail if the file system has insufficient space. CacheManager
    # discovery will ignore this directory.
    TEMPORARY = "UPLOAD"

    @staticmethod
    def delete_if_empty(directory: Path) -> None:
        """Delete a directory only if it exists and is empty.

        NOTE: rmdir technically will fail if the directory isn't empty, but
        this feels safer.

        Any exceptions raised will be propagated.

        Args:
            directory: Directory path
        """
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()

    def __init__(self, options: PbenchServerConfig, logger: Logger):
        """Construct a CacheManager object.

        We don't do any discovery here, because the mutation operations allow
        dynamic minimal discovery to save time. The `full_discovery` method
        allows full discovery when desired.

        Args:
            options: PbenchServerConfig configuration object
            logger: A Pbench python Logger
        """
        self.options: PbenchServerConfig = options
        self.logger: Logger = logger

        # Record the root ARCHIVE directory path
        self.archive_root: Path = self.options.ARCHIVE

        # Record the root BACKUP directory path
        self.backup_root: Path = self.options.BACKUP

        # Record the root CACHE directory path
        self.cache_root: Path = self.options.CACHE

        # Construct an index to refer to discovered controllers
        self.controllers: dict[str, Controller] = {}

        # Construct an index to refer to discovered results tarballs
        # by root tarball name
        self.tarballs: dict[str, Tarball] = {}

        # Construct an index to refer to discovered results tarballs
        # by the tarball MD5 value, corresponding to the dataset formal
        # resource_id.
        self.datasets: dict[str, Tarball] = {}

    def full_discovery(self, search: bool = True) -> "CacheManager":
        """Discover the ARCHIVE and CACHE trees

        Full discovery is only needed for reporting, and is not required
        to find, create, or delete a specific dataset. (See find_dataset.)

        Args:
            search: search the ARCHIVE tree rather than using the Dataset table

        Returns:
            CacheManager instance for chaining
        """
        if search:
            self._discover_controllers()
        else:
            self._discover_datasets()
        return self

    def __contains__(self, dataset_id: str) -> bool:
        """Determine whether the cache manager includes a dataset.

        Args:
            dataset_id: Dataset resource ID

        Returns:
            True if the dataset is present
        """
        return dataset_id in self.datasets

    def __getitem__(self, dataset_id: str) -> Tarball:
        """Find a dataset Tarball object by dataset ID (MD5).

        Args:
            dataset_id: Dataset resource ID

        Returns:
            Tarball object
        """
        try:
            return self.datasets[dataset_id]
        except KeyError:
            raise TarballNotFound(dataset_id) from None

    def _clean_empties(self, controller: str):
        """Remove empty controller directories from the ARCHIVE tree.

        Args:
            controller: Name of the controller to clean up
        """
        archive = self.options.ARCHIVE / controller

        # Look for tarballs in the controller or subdirectory. (NOTE: this
        # provides compatibility with tarballs in an "isolator" subdirectory
        # and older tarballs without isolators by using the recursive "**/"
        # glob syntax.)
        if archive.exists() and not any(archive.glob(f"**/*{Dataset.TARBALL_SUFFIX}")):
            self.delete_if_empty(archive)
            del self.controllers[controller]

    def _add_controller(self, directory: Path, discover: bool = True) -> Controller:
        """Create a new Controller object

        Add a new controller to the set of known controllers, and append the
        discovered datasets (tarballs) to the list of known datasets (by
        internal dataset ID) and tarballs (by tarball base name).

        Args:
            directory: A controller directory within the ARCHIVE tree
            discover: Discover tarballs if True

        Returns:
            The new controller
        """
        controller = Controller(directory, self.options.CACHE, self.logger, discover)
        controller.cache_manager = self
        self.controllers[controller.name] = controller
        self.tarballs.update(controller.tarballs)
        self.datasets.update(controller.datasets)
        return controller

    def _discover_controllers(self):
        """Discover the ARCHIVE tree exhaustively by searching it.

        Record all controllers (top level directories), and the tarballs that
        represent datasets within them.
        """
        for file in self.archive_root.iterdir():
            if file.is_dir() and file.name != CacheManager.TEMPORARY:
                self._add_controller(file)

    def _discover_datasets(self):
        """Discover the ARCHIVE tree from the SQL representation of datasets

        Discover all controllers and tarballs with server.tarball-path
        metadata. This will find only correct and "live" tarballs, and may
        miss incorrectly labeled tarballs. (Unless we're trying to diagnose
        ARCHIVE tree errors, this is probably what we want.)
        """
        rows = (
            Database.db_session.query(
                Dataset.name,
                Dataset.resource_id,
                Metadata.value["tarball-path"].as_string(),
            )
            .execution_options(stream_results=True)
            .outerjoin(
                Metadata,
                and_(Dataset.id == Metadata.dataset_ref, Metadata.key == "server"),
            )
            .yield_per(1000)
        )

        for name, resource_id, path in rows:
            if not path:
                # This runs asychronously with normal operation, and we might
                # find a dataset before the "server.tarball-path" metadata is
                # set. Issue a warning in case this becomes a concern, but
                # otherwise ignore it and skip the dataset.
                self.logger.warning(
                    "query unexpectedly returned name {}, resource_id {}, path {}",
                    name,
                    resource_id,
                    path,
                )
                continue
            tarball = Path(path)
            controller_dir = tarball.parent
            if controller_dir.name == resource_id:
                controller_dir = controller_dir.parent
            controller = self.controllers.get(
                controller_dir.name, self._add_controller(controller_dir, False)
            )
            if controller._add_if_tarball(tarball, resource_id):
                self.tarballs.update(controller.tarballs)
                self.datasets.update(controller.datasets)
            else:
                # This would be abnormal: log it and continue
                self.logger.error(
                    "Unable to add {}: MD5 {}, path {}", name, resource_id, path
                )

    def find_dataset(self, dataset_id: str) -> Tarball:
        """Return a descriptor of the identified tarball.

        This will build the Controller and Tarball object for that dataset if
        they do not already exist.

        This allows a targeted minimal entry for mutation without discovering
        the entire tree.

        Args:
            dataset_id: The resource ID of a dataset that might exist somewhere
                in the cache manager.

        Raises:
            TarballNotFound: the ARCHIVE tree does not contain a tarball that
                corresponds to the dataset name.

        Returns:
            A Tarball object representing the dataset that was found.
        """
        if dataset_id in self.datasets:
            return self.datasets[dataset_id]

        # The dataset isn't already known; so follow the tarball-path to build
        # just the necessary controller and tarball objects.
        start = time.time()
        sql = start
        try:
            dataset = Dataset.query(resource_id=dataset_id)
            sql = time.time()
            tarball = Path(Metadata.getvalue(dataset, Metadata.TARBALL_PATH))
        except Exception as e:
            raise TarballNotFound(dataset_id) from e
        controller_dir = tarball.parent
        if controller_dir.name == dataset_id:
            controller_dir = controller_dir.parent
        found = time.time()
        controller = self.controllers.get(
            controller_dir.name, self._add_controller(controller_dir, False)
        )
        controller._add_if_tarball(tarball, dataset_id)
        self.tarballs.update(controller.tarballs)
        self.datasets.update(controller.datasets)
        add = time.time()
        self.logger.info(
            "{}: {:.3f} to find tarball, {:.3f} SQL, {:.3f} to discover controller",
            dataset.name,
            found - start,
            sql - start,
            add - found,
        )
        return self.datasets[dataset_id]

    # These are wrappers for controller and tarball operations which need to be
    # aware of higher-level constructs in the Pbench Server cache manager such as
    # the ARCHIVE, INCOMING, and RESULTS directory branches. These will manage
    # the higher level environment surrounding the encapsulated class methods.
    #
    # create
    #   Alternate constructor to create a Tarball object and move an incoming
    #   tarball and md5 into the proper controller directory.
    #
    # find_entry
    #   Locate a path within a tarball.
    #
    # get_contents
    #   Return metadata about a path within a tarball.
    #
    # get_inventory
    #   Return a managed byte stream for a file within a tarball.
    #
    # get_inventory_bytes
    #   Return the contents a file within a tarball as a string.
    #
    # delete
    #   Remove the tarball and MD5 file from ARCHIVE after uncaching the
    #   unpacked directory tree.
    #
    # reclaim_cache
    #   Remove cached tarball trees to free disk space.

    def create(self, tarfile_path: Path) -> Tarball:
        """Bring a new tarball under cache manager management.

        Move a dataset tarball and companion MD5 file into the specified
        controller directory. The controller directory will be created if
        necessary.

        Datasets without an identifiable controller will be assigned to
        "unknown".

        Args:
            tarfile_path: dataset tarball path

        Raises
            BadDirpath: Failure on extracting the file from tarball
            MetadataError: Failure on getting metadata from metadata.log file
                in the tarball
            BadFilename: A bad tarball path was given
            DuplicateTarball: A duplicate tarball name was detected

        Returns
            Tarball object
        """
        if not tarfile_path.is_file():
            raise BadFilename(tarfile_path)
        name = Dataset.stem(tarfile_path)
        controller_name = None
        errwhy = "unknown"
        try:
            metadata = Tarball._get_metadata(tarfile_path)
        except Exception as e:
            metadata = None
            errwhy = str(e)
        else:
            run = metadata.get("run")
            if run:
                controller_name = run.get("controller")
                if not controller_name:
                    errwhy = "missing 'controller' in 'run' section"
            else:
                errwhy = "missing 'run' section"

        if not controller_name:
            controller_name = "unknown"
            self.logger.warning(
                "{} has no controller name ({}), assuming {!r}",
                name,
                errwhy,
                controller_name,
            )

        if name in self.tarballs:
            raise DuplicateTarball(name)
        if controller_name in self.controllers:
            controller = self.controllers[controller_name]
        else:
            controller = Controller.create(controller_name, self.options, self.logger)
            self.controllers[controller_name] = controller
        tarball = controller.create_tarball(tarfile_path)
        tarball.metadata = metadata
        self.tarballs[tarball.name] = tarball
        self.datasets[tarball.resource_id] = tarball
        return tarball

    def find_entry(self, dataset_id: str, path: Path) -> dict[str, Any]:
        """Get information about dataset files from the cache map

        Args:
            dataset_id: Dataset resource ID
            path: path of requested content

        Returns:
            File Metadata
        """
        tarball = self.find_dataset(dataset_id)
        return tarball.find_entry(path)

    def get_contents(self, dataset_id: str, path: str, origin: str) -> dict[str, Any]:
        """Get information about dataset files from the cache map

        Args:
            dataset_id: Dataset resource ID
            path: path of requested content
            origin: base URI for links

        Returns:
            contents metadata
        """
        tarball = self.find_dataset(dataset_id)
        return tarball.get_contents(path, origin)

    def get_inventory(self, dataset_id: str, target: str) -> Optional[JSONOBJECT]:
        """Return filestream data for a file within a dataset tarball

            {
                "name": "filename",
                "type": CacheType.FILE,
                "stream": <byte stream>
            }

        Args:
            dataset_id: Dataset resource ID
            target: relative file path within the tarball

        Returns:
            File info including a byte stream for a regular file
        """
        tarball = self.find_dataset(dataset_id)
        return tarball.get_inventory(target)

    def get_inventory_bytes(self, dataset_id: str, target: str) -> str:
        tarball = self.find_dataset(dataset_id)
        info = tarball.get_inventory(target)
        try:
            return info["stream"].read().decode("utf-8")
        except Exception as e:
            raise CacheExtractError(tarball.name, target) from e
        finally:
            info["stream"].close()

    def delete(self, dataset_id: str):
        """Delete the dataset as well as unpacked artifacts.

        Args:
            dataset_id: Dataset resource ID to delete
        """
        try:
            tarball = self.find_dataset(dataset_id)
        except TarballNotFound:
            return
        name = tarball.name
        tarball.controller.delete(dataset_id)
        del self.datasets[dataset_id]
        del self.tarballs[name]

        self._clean_empties(tarball.controller_name)

    def reclaim_cache(self, goal_pct: float = 0.0, goal_bytes: int = 0) -> bool:
        """Reclaim unused caches to free disk space.

        The cache tree need not be fully discovered at this point; we can
        reclaim cache even on a partial tree. This is driven by discovery of
        the cache directory tree, looking for <resource_id> directories that
        contain an unpacked tarball root rather than only the `lock` and
        `last_ref` files.

        This is a "best effort" operation. It will free unlocked caches, oldest
        first, until both the goal % and the absolute goal bytes (rounded up to
        the next megabyte) are available, or until there are no more unlocked
        cached tarballs.

        Args:
            goal_pct: goal percent of cache filesystem free
            goal_bytes: goal in bytes

        Returns:
            True if both goals are met, or False otherwise
        """

        @dataclass
        class Candidate:
            """Keep track of cache reclamation candidates"""

            last_ref: float  # last reference timestamp
            cache: Path  # Unpacked artifact directory

        @dataclass
        class GoalCheck:
            """Report goal check"""

            reached: bool
            usage: shutil._ntuple_diskusage

        def reached_goal() -> GoalCheck:
            """Check whether we've freed enough space"""
            usage = shutil.disk_usage(self.cache_root)
            return GoalCheck(usage.free >= goal, usage)

        # Our reclamation goal can be expressed as % of total, absolute bytes,
        # or both. We normalize to a single "bytes free" goal.
        usage = shutil.disk_usage(self.cache_root)
        pct_as_bytes = math.ceil(usage.total * goal_pct / 100.0)
        bytes_rounded = ((goal_bytes + MB_BYTES) // MB_BYTES) * MB_BYTES
        goal = max(pct_as_bytes, bytes_rounded)

        if usage.free >= goal:
            return True

        total_count = 0
        reclaimed = 0
        reclaim_failed = 0

        # Identify cached datasets by examining the cache directory tree
        candidates = deque()
        for d in self.cache_root.iterdir():
            if not d.is_dir():
                self.logger.warning(
                    "RECLAIM: found unexpected file in cache root: {}", d
                )
                continue
            total_count += 1
            last_ref = 0.0
            unpacked = None
            for f in d.iterdir():
                if f.name == "last_ref":
                    last_ref = f.stat().st_mtime
                elif f.is_dir():
                    unpacked = f
                if last_ref and unpacked:
                    break
            if unpacked:
                candidates.append(Candidate(last_ref, unpacked))

        # Sort the candidates by last_ref timestamp, putting the oldest at
        # the head of the queue. We'll flush each cache tree until we reach
        # our goals.
        candidates = sorted(candidates, key=lambda c: c.last_ref)
        has_cache = len(candidates)
        goal_check = reached_goal()
        for candidate in candidates:
            name = candidate.cache.name
            cache_d = candidate.cache.parent
            resource_id = cache_d.name

            # Only if the dataset we're flushing has already been discovered,
            # we want to update the Tarball object so that we don't break it.
            # If it hasn't been discovered under this cache instance, that's
            # fine because discovery will notice that the cache is empty.
            if resource_id in self.datasets:
                target = self.datasets[resource_id]
            else:
                target = None
            error = None
            try:
                ts = datetime.fromtimestamp(candidate.last_ref)
                self.logger.info(
                    "RECLAIM: removing cache for {} (referenced {})", name, ts
                )
                with LockManager(cache_d / "lock", exclusive=True, wait=False):
                    try:
                        if target:
                            target.cache_delete()
                        else:
                            shutil.rmtree(candidate.cache)
                    except Exception as e:
                        reclaim_failed += 1
                        error = e
                    else:
                        reclaimed += 1
                        goal_check = reached_goal()
                        if goal_check.reached:
                            break
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EACCES):
                    self.logger.info(
                        "RECLAIM: skipping {} because cache is locked", name
                    )
                    # Don't reclaim a cache that's in use
                    continue
                reclaim_failed += 1
                error = e
            except Exception as e:
                reclaim_failed += 1
                error = e
            if error:
                self.logger.error("RECLAIM: {} failed with '{}'", name, error)
        free_pct = goal_check.usage.free * 100.0 / goal_check.usage.total
        self.logger.info(
            "RECLAIM {} (goal {}%, {}): {} datasets, "
            "{} had cache: {} reclaimed and {} errors: {:.1f}% free",
            "achieved" if goal_check.reached else "partial",
            goal_pct,
            humanize.naturalsize(goal_bytes),
            total_count,
            has_cache,
            reclaimed,
            reclaim_failed,
            free_pct,
        )
        return goal_check.reached
