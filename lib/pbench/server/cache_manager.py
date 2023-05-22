from collections import deque
from dataclasses import dataclass
from enum import auto, Enum
from logging import Logger
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
from typing import Optional, Union

from pbench.common import MetadataLog, selinux
from pbench.server import JSONOBJECT, PbenchServerConfig
from pbench.server.database.models.datasets import Dataset
from pbench.server.utils import get_tarball_md5


class CacheManagerError(Exception):
    """Base class for exceptions raised from this module."""

    def __str__(self) -> str:
        return "Generic cache manager exception"


class BadDirpath(CacheManagerError):
    """A bad directory path was given."""

    def __init__(self, error_msg: str):
        self.error_msg = error_msg

    def __str__(self) -> str:
        return self.error_msg


class BadFilename(CacheManagerError):
    """A bad tarball path was given."""

    def __init__(self, path: Union[str, Path]):
        self.path = str(path)

    def __str__(self) -> str:
        return f"The file path {self.path!r} is not a tarball"


class TarballNotFound(CacheManagerError):
    """The dataset was not found in the ARCHIVE tree."""

    def __init__(self, tarball: str):
        self.tarball = tarball

    def __str__(self) -> str:
        return f"The dataset tarball named {self.tarball!r} is not present in the cache manager"


class DuplicateTarball(CacheManagerError):
    """A duplicate tarball name was detected."""

    def __init__(self, tarball: str):
        self.tarball = tarball

    def __str__(self) -> str:
        return f"A dataset tarball named {self.tarball!r} is already present in the cache manager"


class MetadataError(CacheManagerError):
    """A problem was found processing a tarball's metadata.log file."""

    def __init__(self, tarball: Path, error: Exception):
        self.tarball = tarball
        self.error = str(error)

    def __str__(self) -> str:
        return f"A problem occurred processing metadata.log from {self.tarball!s}: {self.error!r}"


class TarballUnpackError(CacheManagerError):
    """An error occured trying to unpack a tarball."""

    def __init__(self, tarball: Path, error: str):
        self.tarball = tarball
        self.error = error

    def __str__(self) -> str:
        return f"An error occurred while unpacking {self.tarball}: {self.error}"


class TarballModeChangeError(CacheManagerError):
    """An error occurred trying to fix unpacked tarball permissions."""

    def __init__(self, tarball: Path, error: str):
        self.tarball = tarball
        self.error = error

    def __str__(self) -> str:
        return f"An error occurred while changing file permissions of {self.tarball}: {self.error}"


class CacheType(Enum):
    FILE = auto()
    DIRECTORY = auto()
    SYMLINK = auto()
    OTHER = auto()


@dataclass
class CacheObject:
    """Initialize CacheObject object with file/Directory info attributes.

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
    resolve_path: Path
    resolve_type: str
    size: int
    type: CacheType


def make_cache_object(dir_path: Path, path: Path) -> CacheObject:
    """Collects the file info

    Args:
        dir_path: root directory parent path
        path: path to a file/directory

    Returns:
        CacheObject with file/directory info
    """
    relative_path: Optional[Path] = None
    resolve_type: Optional[CacheType] = None
    size: Optional[int] = None

    if path.is_symlink():
        ftype = CacheType.SYMLINK
        try:
            link_path = path.readlink()
            if link_path.is_absolute():
                raise ValueError("symlink path is absolute")
            resolve_path = path.resolve(strict=True)
            relative_path = resolve_path.relative_to(dir_path)
        except (FileNotFoundError, ValueError):
            relative_path = link_path
            resolve_type = CacheType.OTHER
        else:
            if resolve_path.is_dir():
                resolve_type = CacheType.DIRECTORY
            elif resolve_path.is_file():
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
        resolve_path=relative_path,
        resolve_type=resolve_type,
        size=size,
        type=ftype,
    )


class Tarball:
    """Representation of an on-disk tarball.

    This class corresponds to the physical representation of a Dataset: the
    tarball, the MD5 file, and unpacked (cached) data.

    It provides discovery and management methods related to a specific
    dataset's on-disk representation. This class does not interact with the
    database representations of a dataset.
    """

    def __init__(self, path: Path, controller: "Controller"):
        """Construct a `Tarball` object instance

        Args:
            path: The file path to a discovered tarball (.tar.xz file) in the
                configured ARCHIVE directory for a controller.
            controller: The associated Controller object
        """
        self.logger: Logger = controller.logger

        # Record the root filename of the tarball
        self.name: str = Dataset.stem(path)

        # Record the Dataset resource ID (MD5) for coordination with the server
        # logic
        self.resource_id: str = get_tarball_md5(path)

        # Record a backlink to the containing controller object
        self.controller: Controller = controller

        # Record the path of the tarball file
        self.tarball_path: Path = path

        # Record where cached unpacked data would live
        self.cache: Path = controller.cache / self.resource_id

        # Record hierarchy of a Tar ball
        self.cachemap: Optional[dict[str, JSONOBJECT]] = None

        # Record the base of the unpacked files for cache management, which
        # is (self.cache / self.name) and will be None when the cache is
        # inactive.
        self.unpacked: Optional[Path] = None

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
    def create(cls, tarball: Path, controller: "Controller") -> "Tarball":
        """An alternate constructor to import a tarball

        This moves a new tarball into the proper place along with the md5
        companion file. It returns the new Tarball object.
        """

        # Validate the tarball suffix and extract the dataset name
        name = Dataset.stem(tarball)

        # NOTE: with_suffix replaces only the final suffix, .xz, not the full
        # standard .tar.xz
        md5_source = tarball.with_suffix(".xz.md5")

        # If either expected destination file exists, something is wrong
        if (controller.path / tarball.name).exists():
            raise DuplicateTarball(name)
        if (controller.path / md5_source.name).exists():
            raise DuplicateTarball(name)

        # Copy the MD5 file first; only if that succeeds, copy the tarball
        # itself.
        try:
            md5_destination = Path(shutil.copy2(md5_source, controller.path))
        except Exception as e:
            controller.logger.error(
                "ERROR copying dataset {} ({}) MD5: {}", name, tarball, e
            )
            raise

        try:
            destination = Path(shutil.copy2(tarball, controller.path))
        except Exception as e:
            try:
                md5_destination.unlink()
            except Exception as e:
                controller.logger.error(
                    "Unable to recover by removing {} MD5 after tarball copy failure: {}",
                    name,
                    e,
                )
            controller.logger.error(
                "ERROR copying dataset {} tarball {}: {}", name, tarball, e
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

        # If we were able to copy both files, remove the originals
        try:
            tarball.unlink()
            md5_source.unlink()
        except Exception as e:
            controller.logger.error("Error removing incoming dataset {}: {}", name, e)

        return cls(destination, controller)

    def cache_map(self, dir_path: Path):
        """Builds Hierarchy structure of a Directory in a Dictionary
        Format.

        Args:
            dir_path: root directory
        """
        root_dir_path = dir_path.parent
        cmap = {dir_path.name: {"details": make_cache_object(root_dir_path, dir_path)}}
        dir_queue = deque([(dir_path, cmap)])
        while dir_queue:
            dir_path, parent_map = dir_queue.popleft()
            tar_n = dir_path.name

            curr = {}
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
    def traverse_cmap(path: Path, cachemap: dict) -> dict[str, dict]:
        """Sequentially traverses the cachemap to find the leaf of a
        relative path reference

        Args:
            path: relative path of the sub-directory/file
            cachemap: dictionary mapping of the root Dicrectory

        Raises:
            BadDirpath if the directory/file path is not valid

        Returns:
            Dictionary with directory/file details or children if present
        """
        file_list = path.parts[:-1]
        f_entries = cachemap

        try:
            for file_l in file_list:
                info = f_entries[file_l]
                if info["details"].type == CacheType.DIRECTORY:
                    f_entries = info["children"]
                else:
                    raise BadDirpath(
                        f"Found a file {file_l!r} where a directory was expected in path {path}"
                    )

            return f_entries[path.name]
        except KeyError as exc:
            raise BadDirpath(f"File/directory {exc} in path {path} not found in cache.")

    def get_info(self, path: Path) -> dict[str, dict]:
        """Returns the details of the given file/directory in dict format

        Args:
            path: path of the file/sub-directory

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
                "resolve_type": type of file/directory after path resolution if path is a symlink
                "size": size of the file
                "type": type of file/directory in the form of CacheType Enum class
                        which contain FILE, DIRECTORY, SYMLINK & OTHER as attributes.
            }
        """
        if str(path).startswith("/"):
            raise BadDirpath(
                f"The directory path {str(path)!r} is an absolute path,"
                " we expect relative path to the root directory."
            )

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
    def extract(tarball_path: Path, path: str) -> Optional[str]:
        """Extract a file from the tarball and return it as a string

        Report failures by raising exceptions.

        Args:
            path: relative path within the tarball of a file

        Raises:
            MetadataError on failure opening the tarball
            TarballUnpackError on failure to extract the named path

        Returns:
            The named file as a string
        """
        try:
            tar = tarfile.open(tarball_path, "r:*")
        except Exception as exc:
            raise MetadataError(tarball_path, exc) from exc
        try:
            return tar.extractfile(path).read().decode()
        except Exception as exc:
            raise TarballUnpackError(tarball_path, f"Unable to extract {path}") from exc

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
        except TarballUnpackError:
            data = None
        if data:
            metadata = MetadataLog()
            metadata.read_string(data)
            metadata = {s: dict(metadata.items(s)) for s in metadata.sections()}
            return metadata
        else:
            return None

    @staticmethod
    def subprocess_run(
        command: str, working_dir: Path, exception: type[CacheManagerError], ctx: Path
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

    def unpack(self):
        """Unpack a tarball into a temporary directory tree

        Unpack the tarball into a temporary cache directory named with the
        tarball's resource_id (MD5).

        This tree will be used for indexing, and then discarded. As we build
        out more of the cache manager, it can also be used to build our initial
        cache map.

        The indexer works off the unpacked data under CACHE, assuming the
        tarball name in all paths (because this is what's inside the tarball).
        Rather than passing the indexer the root `/srv/pbench/.cache` or trying
        to update all of the indexer code (which still jumps back and forth
        between the tarball and the unpacked files), we maintain the "cache"
        directory as two paths: self.cache which is the directory we manage
        here and pass to the indexer (/srv/pbench/.cache/<resource_id>) and
        the actual unpacked root (/srv/pbench/.cache/<resource_id>/<name>).
        """
        self.cache.mkdir(parents=True)

        try:
            tar_command = f"tar -x --no-same-owner --delay-directory-restore --force-local --file='{str(self.tarball_path)}'"
            self.subprocess_run(
                tar_command, self.cache, TarballUnpackError, self.tarball_path
            )

            find_command = "find . ( -type d -exec chmod ugo+rx {} + ) -o ( -type f -exec chmod ugo+r {} + )"
            self.subprocess_run(
                find_command, self.cache, TarballModeChangeError, self.cache
            )
        except Exception:
            shutil.rmtree(self.cache, ignore_errors=True)
            raise
        self.unpacked = self.cache / self.name
        self.cache_map(self.unpacked)

    def uncache(self):
        """Remove the unpacked tarball directory and all contents."""
        self.cachemap = None
        if self.unpacked:
            try:
                shutil.rmtree(self.cache)
                self.unpacked = None
            except Exception as e:
                self.logger.error("incoming remove for {} failed with {}", self.name, e)
                raise

    def delete(self):
        """Delete the tarball and MD5 file from the ARCHIVE tree.

        We'll log errors in deletion, but "succeed" and clear the links to both
        files. There's nothing more we can do.
        """
        self.uncache()
        if self.md5_path:
            try:
                self.md5_path.unlink()
            except Exception as e:
                self.logger.error("archive unlink for {} failed with {}", self.name, e)
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

    def _discover_tarballs(self):
        """Discover the known tarballs

        Look in the ARCHIVE tree's controller directory for tarballs, and add
        them to the known set. We also check for unpacked directories in the
        CACHE tree matching the resource_id of any tarballs we find in order
        to link them.
        """
        for file in self.path.iterdir():
            if file.is_file() and Dataset.is_tarball(file):
                tarball = Tarball(file, self)
                self.tarballs[tarball.name] = tarball
                self.datasets[tarball.resource_id] = tarball
                tarball.check_unpacked()

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

    def create_tarball(self, tarfile: Path) -> Tarball:
        """Create a new dataset tarball object under the controller

        The new tarball object is linked to the controller so we can find it.

        Args:
            tarfile: Path to source tarball file

        Returns:
            Tarball object
        """
        tarball = Tarball.create(tarfile, self)
        self.datasets[tarball.resource_id] = tarball
        self.tarballs[tarball.name] = tarball
        return tarball

    def unpack(self, dataset_id: str):
        """Unpack a tarball into a temporary cache directory.

        Args:
            dataset_id: Resource ID of the dataset to unpack
        """
        tarball = self.datasets[dataset_id]
        tarball.unpack()

    def uncache(self, dataset_id: str):
        """Remove the cached unpack directory.

        Args:
            dataset_id: Resource ID of dataset to remove
        """
        tarball = self.datasets[dataset_id]
        tarball.uncache()

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

    def full_discovery(self):
        """Discover the ARCHIVE and CACHE trees

        NOTE: both _discover_unpacked() and _discover_results() rely on the
        results of _discover_archive(), which must run first.

        Full discovery is not required in order to find, create, or delete a
        specific dataset.
        """
        self._discover_controllers()

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
        if archive.exists() and not any(archive.glob(f"*{Dataset.TARBALL_SUFFIX}")):
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
        that represent datasets within them.
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
        for dir in self.archive_root.iterdir():
            if dir.is_dir() and dir.name != self.TEMPORARY:
                for file in dir.glob(f"*{Dataset.TARBALL_SUFFIX}"):
                    md5 = get_tarball_md5(file)
                    if md5 == dataset_id:
                        self._add_controller(dir)
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

    def create(self, tarfile: Path) -> Tarball:
        """Bring a new tarball under cache manager management.

        Move a dataset tarball and companion MD5 file into the specified
        controller directory. The controller directory will be created if
        necessary.

        Args:
            controller: associated controller name
            tarfile: dataset tarball path

        Returns
            Tarball object
        """
        try:
            metadata = Tarball._get_metadata(tarfile)
            if metadata:
                controller_name = metadata["run"]["controller"]
            else:
                controller_name = "unknown"
        except MetadataError:
            raise
        except Exception as exc:
            raise MetadataError(tarfile, exc)

        if not controller_name:
            raise MetadataError(tarfile, "no controller value")
        if not tarfile.is_file():
            raise BadFilename(tarfile)
        name = Dataset.stem(tarfile)
        if name in self.tarballs:
            raise DuplicateTarball(name)
        if controller_name in self.controllers:
            controller = self.controllers[controller_name]
        else:
            controller = Controller.create(controller_name, self.options, self.logger)
            self.controllers[controller_name] = controller
        tarball = controller.create_tarball(tarfile)
        tarball.metadata = metadata
        self.tarballs[tarball.name] = tarball
        self.datasets[tarball.resource_id] = tarball
        return tarball

    def unpack(self, dataset_id: str) -> Tarball:
        """Unpack a tarball into the CACHE tree

        Args:
            dataset_id: Dataset resource ID

        Returns:
            The tarball object
        """
        tarball = self.find_dataset(dataset_id)
        tarball.controller.unpack(dataset_id)
        return tarball

    def get_info(self, dataset_id: str, path: Path) -> dict:
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

    def uncache(self, dataset_id: str):
        """Remove the unpacked tarball tree.

        Args:
            dataset_id: Dataset resource ID to "uncache"
        """
        tarball = self.find_dataset(dataset_id)
        controller = tarball.controller
        controller.uncache(dataset_id)
        self._clean_empties(controller.name)

    def delete(self, dataset_id: str):
        """Delete the dataset as well as unpacked artifacts.

        Args:
            dataset_id: Dataset resource ID to delete
        """
        try:
            tarball = self.find_dataset(dataset_id)
            name = tarball.name
            tarball.controller.delete(dataset_id)
            del self.datasets[dataset_id]
            del self.tarballs[name]
            self._clean_empties(tarball.controller_name)
        except TarballNotFound:
            return
