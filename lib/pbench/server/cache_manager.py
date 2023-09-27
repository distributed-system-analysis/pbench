from collections import deque
from dataclasses import dataclass
from enum import auto, Enum
import fcntl
from logging import Logger
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from typing import Any, IO, Optional, Union

from pbench.common import MetadataLog, selinux
from pbench.server import JSONOBJECT, OperationCode, PathLike, PbenchServerConfig
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType
from pbench.server import JSONOBJECT, OperationCode, PathLike, PbenchServerConfig
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType
from pbench.server.database.models.datasets import Dataset
from pbench.server.utils import get_tarball_md5


class CacheManagerError(Exception):
    """Base class for exceptions raised from this module."""

    pass
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
            f"A problem occurred processing metadata.log from {tarball}: {str(error)!r}"
        )
        self.tarball = tarball
        self.error = str(error)


class TarballUnpackError(CacheManagerError):
    """An error occurred trying to unpack a tarball."""

    def __init__(self, tarball: Path, error: str):
        super().__init__(f"An error occurred while unpacking {tarball}: {error}")
        self.tarball = tarball
        self.error = error


class TarballModeChangeError(CacheManagerError):
    """An error occurred trying to fix unpacked tarball permissions."""

    def __init__(self, tarball: Path, error: str):
        super().__init__(
            f"An error occurred while changing file permissions of {tarball}: {error}"
        )
        self.tarball = tarball
        self.error = error


class CacheType(Enum):
    FILE = auto()
    DIRECTORY = auto()
    SYMLINK = auto()
    OTHER = auto()


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


# Type hint definitions for the cache map.
#
# CacheMapEntry: { "details": CacheObject, "children": CacheMap }
# CacheMap: { "<directory_entry>": CacheMapEntry, ... }
CacheMapEntry = dict[str, Union[CacheObject, "CacheMap"]]
CacheMap = dict[str, CacheMapEntry]


def make_cache_object(dir_path: Path, path: Path) -> CacheObject:
    """Collects the file info

    Args:
        dir_path: root directory parent path
        path: path to a file/directory

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
                raise ValueError("symlink path is absolute")
            r_path = path.resolve(strict=True)
            resolve_path = r_path.relative_to(dir_path)
        except (FileNotFoundError, ValueError):
            resolve_path = link_path
            resolve_type = CacheType.OTHER
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

    return CacheObject(
        name=path.name,
        location=path.relative_to(dir_path),
        resolve_path=resolve_path,
        resolve_type=resolve_type,
        size=size,
        type=ftype,
    )


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
            lock: a cache lock reference
            subproc: a Popen object to clean up on close
        """
        self.stream = stream
        self.lock = lock
        self.subproc = subproc

    def close(self):
        """Close the byte stream and clean up the Popen object"""

        exception = None

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
        self.cachemap: Optional[CacheMap] = None

        # Record the base of the unpacked files for cache management, which
        # is (self.cache / self.name) and will be None when the cache is
        # inactive.
        self.unpacked: Optional[Path] = None

        # Record the lockf file path used to control cache access
        self.lock: Path = self.cache / "lock"

        # Record a marker file path used to record the last cache access
        # timestamp
        self.last_ref: Path = self.cache / "last_ref"

        # Record the path of the companion MD5 file
        self.md5_path: Path = path.with_suffix(".xz.md5")

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

    def cache_map(self, dir_path: Path):
        """Build hierarchical representation of results tree

        NOTE: this structure isn't removed when we release the cache, as the
        data remains valid.

        Args:
            dir_path: root directory
        """
        root_dir_path = dir_path.parent
        cmap: CacheMap = {
            dir_path.name: {"details": make_cache_object(root_dir_path, dir_path)}
        }
        dir_queue = deque(((dir_path, cmap),))
        while dir_queue:
            dir_path, parent_map = dir_queue.popleft()
            tar_n = dir_path.name

            curr: CacheMapEntry = {}
            for l_path in dir_path.glob("*"):
                tar_info = make_cache_object(root_dir_path, l_path)
                curr[l_path.name] = {"details": tar_info}
                if l_path.is_symlink():
                    continue
                if l_path.is_dir():
                    dir_queue.append((l_path, curr))
            parent_map[tar_n]["children"] = curr

        self.cachemap = cmap

    @staticmethod
    def traverse_cmap(path: Path, cachemap: CacheMap) -> CacheMapEntry:
        """Locate a path in the cache map

        Args:
            path: relative path of the subdirectory/file
            cachemap: dictionary mapping of the root directory

        Raises:
            BadDirpath if the directory/file path is not valid

        Returns:
            Dictionary with directory/file details or children if present
        """
        file_list = path.parts[:-1]
        f_entries = cachemap

        try:
            for file_l in file_list:
                info: CacheMapEntry = f_entries[file_l]
                if info["details"].type == CacheType.DIRECTORY:
                    f_entries: CacheMap = info["children"]
                else:
                    raise BadDirpath(
                        f"Found a file {file_l!r} where a directory was expected in path {str(path)!r}"
                    )
            return f_entries[path.name]
        except KeyError as exc:
            raise BadDirpath(
                f"directory {str(path)!r} doesn't have a {exc} file/directory."
            )

    def get_info(self, path: Path) -> JSONOBJECT:
        """Returns the details of the given file/directory in dict format

        NOTE: If the cache manager doesn't already have a cache map for the
        current Tarball, we'll unpack it here; however as the cache map isn't
        dependent on the unpacked results tree, we immediately release the
        cache lock.

        Args:
            path: path of the file/subdirectory

        Raises:
            BadDirpath on bad directory path

        Returns:
            Dictionary with Details of the file/directory

            format:
            {
                "directories": list of subdirectories under the given directory
                "files": list of files under the given directory
                "location": relative path to the given file/directory
                "name": name of the file/directory
                "resolve_path": resolved path of the file/directory if given path is a symlink
                "resolve_type": CacheType describing the type of the symlink target
                "size": size of the file
                "type": CacheType describing the type of the file/directory
            }
        """
        if str(path).startswith("/"):
            raise BadDirpath(
                f"The path {str(path)!r} is an absolute path,"
                " we expect relative path to the root directory."
            )

        if not self.cachemap:
            with LockManager(self.lock) as lock:
                self.get_results(lock)

        c_map = self.traverse_cmap(path, self.cachemap)
        children = c_map["children"] if "children" in c_map else {}
        fd_info = c_map["details"].__dict__.copy()

        if fd_info["type"] == CacheType.DIRECTORY:
            fd_info["directories"] = []
            fd_info["files"] = []

            for key, value in children.items():
                if value["details"].type == CacheType.DIRECTORY:
                    fd_info["directories"].append(key)
                elif value["details"].type == CacheType.FILE:
                    fd_info["files"].append(key)

            fd_info["directories"].sort()
            fd_info["files"].sort()

        return fd_info

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

    def stream(self, path: str) -> Inventory:
        """Return a cached inventory file as a binary stream

        Args:
            path: Relative path of a regular file within a tarball.

        On failure, an exception is raised and the cache lock is released; on
        success, returns an Inventory object which implicitly transfers
        ownership and management of the cache lock to the caller. When done
        with the inventory's file stream, the caller must close the Inventory
        object to release the file stream and the cache lock.

        Raises:
            CacheExtractBadPath: the path does not match a regular file within
                the tarball.

        Returns:
            An Inventory object encapsulating the file stream and the cache
            lock.
        """

        with LockManager(self.lock) as lock:
            artifact: Path = self.get_results(lock) / path
            if not artifact.is_file():
                raise CacheExtractBadPath(self.tarball_path, path)
            return Inventory(artifact.open("rb"), lock=lock.keep())

    def get_inventory(self, path: str) -> Optional[JSONOBJECT]:
        """Access the file stream of a tarball member file.

        Args:
            path: relative path within the tarball of a file

        Returns:
            Dictionary with file info and file stream
        """
        if not path:
            info = {
                "name": self.tarball_path.name,
                "type": CacheType.FILE,
                "stream": Inventory(self.tarball_path.open("rb")),
            }
        else:
            stream = self.stream(path)
            info = {"name": path, "type": CacheType.FILE, "stream": stream}

        return info

    @staticmethod
    def _get_metadata(tarball_path: Path) -> Optional[JSONOBJECT]:
        """Fetch the values in metadata.log from the tarball.

        Returns:
            A JSON representation of the dataset `metadata.log` or None if the
            tarball has no metadata.log.
        """
        name = Dataset.stem(tarball_path)
        try:
            data = Tarball.extract(tarball_path, f"{name}/metadata.log")
        except CacheExtractBadPath:
            return None
        else:
            metadata_log = MetadataLog()
            metadata_log.read_file(e.decode() for e in data)
            data.close()
            metadata = {s: dict(metadata_log.items(s)) for s in metadata_log.sections()}
            return metadata

    @staticmethod
    def subprocess_run(
        command: str,
        working_dir: PathLike,
        exception: type[CacheManagerError],
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
                raise exception(
                    ctx,
                    f"{cmd[0]} exited with status {process.returncode}:  {process.stderr.strip()!r}",
                )

    def get_results(self, lock: LockManager) -> Path:
        """Unpack a tarball into a temporary directory tree

        Make sure that the dataset results are unpacked into a cache tree. The
        location of the unpacked tree is in self.unpacked and is also returned
        direct to the caller.

        Args:
            lock:   A lock context manager in shared lock state

        Returns:
            the root Path of the unpacked directory tree
        """

        if not self.unpacked:
            lock.upgrade()
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
                self.cache_map(self.unpacked)
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
                        attributes=attributes,
                    )
                lock.downgrade()
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
        self.cache_delete()
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

    def __init__(self, path: Path, cache: Path, logger: Logger):
        """Manage the representation of a controller archive on disk.

        In this context, the path parameter refers to a controller directory
        within the configured ARCHIVE tree. There need not be any files or
        directories related to this controller at this time.

        Args:
            path: Controller ARCHIVE directory path
            cache: The base of the cache tree
            logger: Logger object
        """
        self.logger = logger

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
        self._discover_tarballs()

    def _add_if_tarball(self, file: Path, md5: Optional[str] = None):
        """Check for a tar file, and create an object

        Args:
            file: path of potential tarball
            md5: known MD5 hash, or None to compute here
        """
        if file.is_file() and Dataset.is_tarball(file):
            hash = md5 if md5 else get_tarball_md5(file)
            tarball = Tarball(file, hash, self)
            self.tarballs[tarball.name] = tarball
            self.datasets[tarball.resource_id] = tarball
            tarball.check_unpacked()

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

    def full_discovery(self) -> "CacheManager":
        """Discover the ARCHIVE and CACHE trees

        NOTE: both _discover_unpacked() and _discover_results() rely on the
        results of _discover_archive(), which must run first.

        Full discovery is not required in order to find, create, or delete a
        specific dataset.
        """
        self._discover_controllers()
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

    def _add_controller(self, directory: Path) -> None:
        """Create a new Controller object

        Add a new controller to the set of known controllers, and append the
        discovered datasets (tarballs) to the list of known datasets (by
        internal dataset ID) and tarballs (by tarball base name).

        Args:
            directory: A controller directory within the ARCHIVE tree
        """
        controller = Controller(directory, self.options.CACHE, self.logger)
        self.controllers[controller.name] = controller
        self.tarballs.update(controller.tarballs)
        self.datasets.update(controller.datasets)

    def _discover_controllers(self):
        """Build a representation of the ARCHIVE tree

        Record all controllers (top level directories), and the tarballs that
        represent datasets within them.
        """
        for file in self.archive_root.iterdir():
            if file.is_dir() and file.name != CacheManager.TEMPORARY:
                self._add_controller(file)

    def find_dataset(self, dataset_id: str) -> Tarball:
        """Search the ARCHIVE tree for a matching dataset tarball.

        This will build the Controller and Tarball object for that dataset if
        they do not already exist.

        FIXME: This builds the entire Controller, which will discover all
        datasets within the controller. This could be streamlined.

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

        # The dataset isn't already known; so search for it in the ARCHIVE tree
        # and (if found) discover the controller containing that dataset.
        for dir_entry in self.archive_root.iterdir():
            if dir_entry.is_dir() and dir_entry.name != self.TEMPORARY:
                for file in dir_entry.glob(f"**/*{Dataset.TARBALL_SUFFIX}"):
                    md5 = get_tarball_md5(file)
                    if md5 == dataset_id:
                        self._add_controller(dir_entry)
                        return self.datasets[dataset_id]
        raise TarballNotFound(dataset_id)

    # These are wrappers for controller and tarball operations which need to be
    # aware of higher-level constructs in the Pbench Server cache manager such as
    # the ARCHIVE, INCOMING, and RESULTS directory branches. These will manage
    # the higher level environment surrounding the encapsulated class methods.
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
    #   Remove the unpacked directory tree when no longer needed.
    #
    # delete
    #   Remove the tarball and MD5 file from ARCHIVE after uncaching the
    #   unpacked directory tree.

    def create(self, tarfile_path: Path) -> Tarball:
        """Bring a new tarball under cache manager management.

        Move a dataset tarball and companion MD5 file into the specified
        controller directory. The controller directory will be created if
        necessary.

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
        try:
            metadata = Tarball._get_metadata(tarfile_path)
            if metadata:
                controller_name = metadata["run"]["controller"]
            else:
                controller_name = "unknown"
        except Exception as exc:
            raise MetadataError(tarfile_path, exc)

        if not controller_name:
            raise MetadataError(tarfile_path, ValueError("no controller value"))
        if not tarfile_path.is_file():
            raise BadFilename(tarfile_path)
        name = Dataset.stem(tarfile_path)
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

    def get_info(self, dataset_id: str, path: Path) -> dict[str, Any]:
        """Get information about dataset files from the cache map

        Args:
            dataset_id: Dataset resource ID
            path: path of requested content

        Returns:
            File Metadata
        """
        tarball = self.find_dataset(dataset_id)
        tmap = tarball.get_info(path)
        return tmap

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
