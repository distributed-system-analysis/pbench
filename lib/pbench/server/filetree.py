from configparser import ConfigParser
from logging import Logger
from pathlib import Path
import re
import shutil
import tarfile
from typing import Dict, Optional, Union

from pbench.common import selinux
from pbench.server import JSONOBJECT, PbenchServerConfig
from pbench.server.database.models.datasets import Dataset
from pbench.server.utils import get_tarball_md5


class FiletreeError(Exception):
    """
    Base class for exceptions raised from this code.
    """

    def __str__(self) -> str:
        return "Generic file tree exception"


class BadFilename(FiletreeError):
    """
    A bad path is given for a tarball.
    """

    def __init__(self, path: Union[str, Path]):
        self.path = str(path)

    def __str__(self) -> str:
        return f"The file path {self.path!r} is not a tarball"


class TarballNotFound(FiletreeError):
    """
    The on-disk representation of a dataset (tarball and MD5 companion) were
    not found in the ARCHIVE tree.
    """

    def __init__(self, tarball: str):
        self.tarball = tarball

    def __str__(self) -> str:
        return f"The dataset tarball named {self.tarball!r} is not present in the file tree"


class DuplicateTarball(FiletreeError):
    """
    A duplicate tarball name was detected.
    """

    def __init__(self, tarball: str):
        self.tarball = tarball

    def __str__(self) -> str:
        return f"A dataset tarball named {self.tarball!r} is already present in the file tree"


class MetadataError(FiletreeError):
    """
    A problem was found locating or processing a tarball's metadata.log file.
    """

    def __init__(self, tarball: Path, error: Exception):
        self.tarball = tarball
        self.error = str(error)

    def __str__(self) -> str:
        return f"A problem occurred processing metadata.log from {self.tarball!s}: {self.error!r}"


class Tarball:
    """
    This class corresponds to the physical representation of a Dataset: the
    tarball, the MD5 file, and the unpacked data.

    It provides discovery and management methods related to a specific
    dataset's on-disk representation. This class does not interact with the
    database representations of a dataset.
    """

    def __init__(self, path: Path, controller: "Controller"):
        """
        Construct a `Tarball` object instance representing a the file system
        artifacts of a dataset.

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

        # Record the unpacked INCOMING tree directory
        self.unpacked: Optional[Path] = None

        # Record the RESULTS tree softlink path
        self.results_link: Optional[Path] = None

        # Record the path of the companion MD5 file
        self.md5_path: Path = path.with_suffix(".xz.md5")

        # Record the name of the containing controller
        self.controller_name: str = controller.name

        # Cache results metadata when it's been processed
        self.metadata: Optional[JSONOBJECT] = None

    def check_unpacked(self, incoming: Path) -> bool:
        """
        Determine whether a tarball in the ARCHIVE tree has been unpacked into
        the INCOMING tree and if so record the link.

        Args
            result:   The controller's RESULTS directory

        Return
            True if an unpacked directory was discovered
        """
        dir = incoming / self.name
        if dir.is_dir():
            self.unpacked = dir
            return True
        return False

    def check_results(self, result: Path) -> bool:
        """
        Determine whether a tarball in the ARCHIVE tree has a RESULTS tree link
        to an unpacked INCOMING tree and if so record the link.

        Args
            result:   The controller's RESULTS directory

        Return
            True if a results link was discovered
        """
        dir = result / self.name
        if dir.is_symlink():
            self.results_link = dir
            return True
        return False

    # Most of the "operational" methods below this point should be called only
    # through Controller and/or FileTree methods, in order to properly manage
    # aspects of the file tree structure outside the scope of the Tarball.
    #
    # create
    #   Alternate constructor to create a Tarball object and move an incoming
    #   tarball and md5 into the proper controller directory.
    #
    # unpack
    #   Unpack the ARCHIVE tarball file into a new directory under the
    #   controller directory in the INCOMING directory tree.
    #
    # uncache
    #   Remove the unpacked directory tree under INCOMING when no longer needed.
    #
    # delete
    #   Remove the tarball and MD5 file from ARCHIVE after uncaching the
    #   unpacked directory tree.

    @classmethod
    def create(cls, tarball: Path, controller: "Controller") -> "Tarball":
        """
        This is an alternate constructor to move an incoming tarball into the
        proper place along with the md5 companion file. It returns the new
        Tarball object.
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

        # To get the new tarball into the server pipeline, we start with a
        # symlink in the TODO state directory.
        #
        # NOTE: there's not much we can do if the link fails, except report it.
        # The solution is for someone to manually create the link to oil the
        # tool chain machinery. It doesn't make sense to fail and back out at
        # this point, and there's no place to report the error aside from the
        # log.
        try:
            controller.link(destination, "TODO")
        except Exception as e:
            controller.logger.error(
                "Failed to link dataset {} into TODO state directory: {}", name, e
            )

        # If we were able to copy both files, remove the originals
        try:
            tarball.unlink()
            md5_source.unlink()
        except Exception as e:
            controller.logger.error("Error removing incoming dataset {}: {}", name, e)

        return cls(destination, controller)

    def extract(self, path: str) -> str:
        """
        Extract a file from the tarball and return it as a string

        Args:
            path: relative path within the tarball of a file

        Raises:
            MetadataError if an exception occurs unpacking the tarball

        Returns:
            The named file as a string
        """
        try:
            return (
                tarfile.open(self.tarball_path, "r:*").extractfile(path).read().decode()
            )
        except Exception as exc:
            raise MetadataError(self.tarball_path, exc)

    def get_metadata(self) -> JSONOBJECT:
        """
        Fetch the values in metadata.log from the tarball, and return a JSON
        document organizing the metadata by section.

        The information is unpacked and processed once, and cached.

        Returns:
            A JSON representation of the dataset `metadata.log`
        """
        if not self.metadata:
            data = self.extract(f"{self.name}/metadata.log")
            metadata = ConfigParser()
            metadata.read_string(data)
            self.metadata = {s: dict(metadata.items(s)) for s in metadata.sections()}
        return self.metadata

    def unpack(self, incoming: Path, results: Path):
        """
        Unpack a tarball into the INCOMING directory tree; this assumes that
        the INCOMING controller directory already exists, which should be
        ensured by calling this indirectly through the Controller class unpack
        method.

        TODO: This is a prototype for testing, and doesn't actually unpack
        the tarball as we're going to be relying on the current unpack pipeline
        command for some time.

        Args:
            incoming: Controller's directory in the INCOMING tree
            results: Controller's directory in the RESULTS tree
        """
        self.logger.warning("Tarball unpack is not yet implemented")
        unpacked = incoming / self.name
        unpacked.mkdir(parents=True)  # Just create an empty directory for now
        self.unpacked = unpacked
        results_link = results / self.name
        results_link.symlink_to(unpacked)
        self.results_link = results_link

    def uncache(self):
        """
        Remove the unpacked tarball directory and all contents. The caller
        is responsible for removing empty controller directories.
        """
        if self.unpacked:
            try:
                shutil.rmtree(self.unpacked)
                self.unpacked = None
            except Exception as e:
                self.logger.error("incoming remove for {} failed with {}", self.name, e)
                raise
        if self.results_link:
            try:
                self.results_link.unlink()
                self.results_link = None
            except Exception as e:
                self.logger.error("results unlink for {} failed with {}", self.name, e)
                raise

    def delete(self):
        """
        Delete the tarball and MD5 file from the ARCHIVE tree.

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
    """
    Record the existence of a "controller" in the ARCHIVE directory tree: this
    only means that a directory was found within the root ARCHIVE directory. A
    controller with no data will be ignored in most contexts, but the audit
    report generator will flag it.
    """

    # List of the state directories under controller in which we record the
    # "state" of tarballs via symlinks. The FileTree package can discover,
    # validate, and report on these.
    STATE_DIRS = [
        "BACKED-UP",
        "BACKUP-FAILED",
        "BAD-MD5",
        "COPIED-SOS",
        "INDEXED",
        "TO-BACKUP",
        "TO-COPY-SOS",
        "TO-DELETE",
        "TODO",
        "TO-INDEX",
        "TO-INDEX-TOOL",
        "TO-LINK",
        "TO-RE-INDEX",
        "TO-UNPACK",
        "TO-SYNC",
        "SYNCED",
        "UNPACKED",
        r"WONT-INDEX(\.\d+)",
        "WONT-UNPACK",
    ]

    @staticmethod
    def delete_if_empty(directory: Path) -> None:
        """
        Delete a directory only if it exists and is empty.

        NOTE: rmdir technically will fail if the directory isn't empty, but
        this feels safer.

        Any exceptions raised will be propagated.

        Args:
            directory: Directory path
        """
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()

    @staticmethod
    def is_statedir(directory: Path) -> bool:
        """
        Determine whether the path represents a known state directory.

        Most of the standard Pbench state directories are fixed strings, but
        `WONT-INDEX` can be suffixed with ".n" where "n" is a pbench_index
        error exit code.

        Args:
            directory: A directory path

        Returns:
            True if the path represents a Pbench state directory
        """
        if not directory.is_dir():
            return False
        name = directory.name
        for state in Controller.STATE_DIRS:
            if re.fullmatch(state, name):
                return True
        return False

    def __init__(self, path: Path, incoming: Path, results: Path, logger: Logger):
        """
        Manage the representation of a controller on disk, which is a set of
        directories; one each in the ARCHIVE, INCOMING, and RESULTS trees.

        In this context, the path parameter refers to a controller directory
        within the configured ARCHIVE tree; "incoming" and "results" refer to
        the configured base directories of INCOMING and RESULTS trees,
        respectively. There need not be any files or directories related to
        this controller within those trees at this time.

        Args:
            path: Controller ARCHIVE directory path
            incoming: The root of the INCOMING tree
            results: The root of the RESULTS tree
            logger: Logger object
        """
        self.logger = logger

        # The controller file system (directory) name
        self.name = path.name

        # The full controller path in the ARCHIVE tree
        self.path = path

        # The set of state directories associated with the controller
        self.state_dirs: Dict[str, Path] = {}

        # Provide a mapping from Tarball file name to object
        self.tarballs: Dict[str, Tarball] = {}

        # Provide a mapping from Dataset resource ID to object
        self.datasets: Dict[str, Tarball] = {}

        # The directory where the tarball will be unpacked
        self.incoming: Path = incoming / self.name

        # A path that will link to the unpacked tarball
        self.results: Path = results / self.name
        self._discover_tarballs()

    def _discover_tarballs(self):
        """
        Discover the tarballs and state directories within the ARCHIVE tree's
        controller directory. Check for an unpacked tarball in the INCOMING
        tree and if that's present also check for a RESULTS tree link.
        """
        for file in self.path.iterdir():
            if self.is_statedir(file):
                self.state_dirs[file.name] = file
            elif file.is_file() and Dataset.is_tarball(file):
                tarball = Tarball(file, self)
                self.tarballs[tarball.name] = tarball
                self.datasets[tarball.resource_id] = tarball
                if tarball.check_unpacked(self.incoming):
                    tarball.check_results(self.results)

    @classmethod
    def create(
        cls, name: str, options: PbenchServerConfig, logger: Logger
    ) -> "Controller":
        """
        Create a new controller directory under the ARCHIVE tree if one doesn't
        already exist, and return a Controller object.

        Returns:
            Controller object
        """
        controller_dir = options.ARCHIVE / name
        controller_dir.mkdir(exist_ok=True, mode=0o755)
        (controller_dir / "TODO").mkdir(exist_ok=True)
        return cls(controller_dir, options.INCOMING, options.RESULTS, logger)

    def create_tarball(self, tarfile: Path) -> Tarball:
        """
        Create a new dataset tarball object under the controller, link it to
        the controller, and return the new Tarball object.

        Args:
            tarfile: Path to source tarball file

        Returns:
            Tarball object
        """
        tarball = Tarball.create(tarfile, self)
        self.datasets[tarball.resource_id] = tarball
        self.tarballs[tarball.name] = tarball
        return tarball

    def link(self, tarfile: Path, state: str):
        """
        Create a state link within the controller sub-tree.

        Args:
            tarball: Tarball path
            state: State directory name (e.g., "TODO")
        """
        (self.state_dirs[state] / tarfile.name).symlink_to(tarfile)

    def unpack(self, dataset_id: str):
        """
        Unpack a tarball into the INCOMING tree. Create the INCOMING controller
        directory if necessary, along with the RESULTS tree link.

        NOTE: This does not not preserve the 0.69 --prefix and --user behaviors
        which alter the RESULTS tree directory structure and maintain an
        additional USERS tree; these are not useful or desirable for 1.0 with
        real users and metadata support.

        Args:
            dataset_id: Resource ID of the dataset to unpack
        """
        tarball = self.datasets[dataset_id]
        self.incoming.mkdir(exist_ok=True)
        self.results.mkdir(exist_ok=True)
        tarball.unpack(self.incoming, self.results)

    def uncache(self, dataset_id: str):
        """
        The reverse of `unpack`, removing the RESULTS tree link and the
        unpacked tarball contents from INCOMING.

        Args:
            dataset_id: Resource ID of dataset to remove
        """
        tarball = self.datasets[dataset_id]
        tarball.uncache()
        self.delete_if_empty(self.results)
        self.delete_if_empty(self.incoming)

    def delete(self, dataset_id: str):
        """
        Delete a dataset tarball and remove it from the controller. This will
        also remove any links to the dataset tarball from the controller's
        state directories.

        Args:
            dataset_id: Resource ID of dataset to delete
        """
        tarball = self.datasets[dataset_id]
        name = tarball.name
        for file in self.path.iterdir():
            if Controller.is_statedir(file):
                for link in file.iterdir():
                    if link.samefile(tarball.tarball_path):
                        link.unlink()
        tarball.delete()
        del self.datasets[dataset_id]
        del self.tarballs[name]


class FileTree:
    """
    A hierarchical representation of the Pbench Server's file structure.

    There are three main trees, which we designate ARCHIVE, INCOMING, and
    RESULTS.

    ARCHIVE

        The ARCHIVE tree is specified by the pbench-archive-dir variable in the
        pbench-server-default.cfg file. The normal value is rooted under the
        designated pbench-top-dir, conventionally something like

            /srv/pbench/archive/fs-version-001/

        This directory is linked from /var/www/html/pbench-tarballs for Apache
        access.

        A directory is created under this root for each controller name used by
        a dataset. Within each ARCHIVE controller directory you'll find:

            A set of Pbench Agent dataset results, each comprising a ".tar.xz"
            tar archive (conventionally referred to as a "tarball") and a
            ".tar.xz.md5" MD5 file with the same base name.

            A set of "state" directories (TODO, etc.) which are used by the
            server tool chain to track the progression of datasets. Each will
            contain absolute symlinks to a tarball within the controller
            directory. There are many, but the main ones are

                TODO indicates an action for the dispatcher, including when a
                tarball is first uploaded;

                TO-UNPACK indicates a tarball that needs to be unpacked;

                TO-INDEX indicates a tarball that needs to be indexed;

                TO-INDEX-TOOLS indicates a tarball that's had its basic content
                indexed but needs extended tools data indexed. (We don't
                routinely do tool indexing, so this will generally have links
                for each tarball in the controller, which are created but then
                ignored.)

    INCOMING

        The INCOMING tree is rooted under the Pbench "top dir" public_html
        directory, conventionally something like

            /srv/pbench/public_html/incoming/

        It's also linked from /var/www/html/incoming.

        Like the ARCHIVE tree, it will contain a directory for each controller;
        but a controller has a subdirectory for each dataset result, with the
        root name of the tarball (without the trailing `.tar.xz`), that
        contains the unpacked contents of the tarball.

        This exists only after the pbench-unpack-tarballs script has run (based
        on the TO-UNPACK state link).

    RESULTS

        The RESULTS tree is rooted under the Pbench "top dir" public_html
        directory, conventionally something like

            /srv/pbench/public_html/results/

        It's also linked from /var/www/html/results.

        This is almost a mirror of the INCOMING tree structure, except that,
        instead of directories containing unpacked tarballs, the RESULTS tree
        contains only a symlink for each dataset name to the INCOMING tree's
        unpacked tarball directory.

        The link is created when each tarball is unpacked, and gives the normal
        reference path for unpacked results data (usually through the link at
        /var/www/html/results).

        NOTE: Under 0.69, the directory structure here is influenced by the
        "prefix" string in the dataset's metadata.log file, and that's the main
        reason for this tree's existence. We don't support the prefix under
        1.0 except as an item of metadata. This makes the RESULTS tree somewhat
        redundant, but there's little point in removing it until we move away
        from the file system entirely and replace it with an object store
        schema.
    """

    # The FileTree class provides a definition of a directory at the same level
    # as "controller" directories, where `PUT` will temporarily store uploaded
    # tarballs and generated MD5 files.
    #
    # Placing this within the ARCHIVE tree ensures that we can rename files to
    # a controller directory instead of copying them, and the upload will
    # already fail if the file system has insufficient space. FileTree
    # discovery will ignore this directory.
    TEMPORARY = "UPLOAD"

    @staticmethod
    def delete_if_empty(directory: Path) -> None:
        """
        Delete a directory only if it exists and is empty.

        NOTE: rmdir technically will fail if the directory isn't empty, but
        this feels safer.

        Any exceptions raised will be propagated.

        Args:
            directory: Directory path
        """
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()

    def __init__(self, options: PbenchServerConfig, logger: Logger):
        """
        Construct a FileTree object. We don't do any discovery here, because
        the mutation operations allow dynamic minimal discovery to save on
        some time. The `full_discovery` method allows full discovery when
        desired.

        Args:
            options: PbenchServerConfig configuration object
            logger: A Pbench python Logger
        """
        self.options: PbenchServerConfig = options
        self.logger: Logger = logger

        # Record the root ARCHIVE directory path
        self.archive_root: Path = self.options.ARCHIVE

        # Record the root INCOMING directory path
        self.incoming_root: Path = self.options.INCOMING

        # Record the root RESULTS directory path
        self.results_root: Path = self.options.RESULTS

        # Construct an index to refer to discovered controllers
        self.controllers: Dict[str, Controller] = {}

        # Construct an index to refer to discovered results tarballs
        # by root tarball name
        self.tarballs: Dict[str, Tarball] = {}

        # Construct an index to refer to discovered results tarballs
        # by the tarball MD5 value, corresponding to the dataset formal
        # resource_id.
        self.datasets: Dict[str, Tarball] = {}

    def full_discovery(self):
        """
        We discover the ARCHIVE, INCOMING, and RESULTS trees as defined by the
        pbench-server.cfg file.

        NOTE: both _discover_unpacked() and _discover_results() rely on the
        results of _discover_archive(), which must run first.

        Full discovery is not required in order to find, create, or delete a
        specific dataset.
        """
        self._discover_controllers()

    def __contains__(self, dataset_id: str) -> bool:
        """
        Allow asking whether a FileTree contains an entry for a specific
        dataset.

        Args:
            dataset_id: Dataset resource ID

        Returns:
            True if the dataset is present
        """
        return dataset_id in self.datasets

    def __getitem__(self, dataset_id: str) -> Tarball:
        """
        Direct access to a dataset Tarball object by dataset ID (MD5).

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
        """
        Remove empty controller directories from the RESULTS and INCOMING
        trees. If there are no remaining tarballs in the ARCHIVE controller
        directory, remove all empty state subdirectories; and, if the
        controller directory is now empty remove it as well.

        Args:
            controller: Name of the controller to clean up
        """
        results = self.options.RESULTS / controller
        self.delete_if_empty(results)
        incoming = self.options.INCOMING / controller
        self.delete_if_empty(incoming)
        archive = self.options.ARCHIVE / controller
        if archive.exists() and not any(archive.glob(f"*{Dataset.TARBALL_SUFFIX}")):
            for file in archive.iterdir():
                if Controller.is_statedir(file):
                    self.delete_if_empty(file)
            self.delete_if_empty(archive)
            del self.controllers[controller]

    def _add_controller(self, directory: Path) -> None:
        """
        Create a new Controller object, add it to the set of known controllers,
        and append the discovered datasets (tarballs) to the list of known
        datasets (by internal dataset ID) and tarballs (by tarball base name).

        Args:
            directory: A controller directory within the ARCHIVE tree
        """
        controller = Controller(
            directory, self.options.INCOMING, self.options.RESULTS, self.logger
        )
        self.controllers[controller.name] = controller
        self.tarballs.update(controller.tarballs)
        self.datasets.update(controller.datasets)

    def _discover_controllers(self):
        """
        Build a representation of the ARCHIVE tree, recording controllers (top
        level directories), the tarballs and MD5 files that represent datasets,
        and the server chain "state" directories.
        """
        for file in self.archive_root.iterdir():
            if file.is_dir() and file.name != FileTree.TEMPORARY:
                self._add_controller(file)

    def find_dataset(self, dataset_id: str) -> Tarball:
        """
        Given the resource ID of a dataset, search the ARCHIVE tree for a
        controller with a matching dataset results MD5 value. This will build
        the Controller and Tarball object for that dataset if they do not
        already exist.

        FIXME: This builds the entire Controller, which will discover all
        datasets within the controller. This could be streamlined... however
        for create and delete, we need to know the state link directories.

        This allows a targeted minimal entry for mutation without discovering
        the entire tree.

        Args:
            dataset_id: The resource ID of a dataset that might exist somewhere
                in the file tree

        Raises:
            TarballNotFound: the ARCHIVE tree does not contain a tarball that
                corresponds to the dataset name

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
    # aware of higher-level constructs in the Pbench Server file tree such as
    # the ARCHIVE, INCOMING, and RESULTS directory branches. These will manage
    # the higher level environment surrounding the encapsulated class methods.
    #
    # create
    #   Alternate constructor to create a Tarball object and move an incoming
    #   tarball and md5 into the proper controller directory.
    #
    # unpack
    #   Unpack the ARCHIVE tarball file into a new directory under the
    #   controller directory in the INCOMING directory tree.
    #
    # uncache
    #   Remove the unpacked directory tree under INCOMING when no longer needed.
    #
    # delete
    #   Remove the tarball and MD5 file from ARCHIVE after uncaching the
    #   unpacked directory tree.

    def create(self, controller_name: str, tarfile: Path) -> Tarball:
        """
        Move a dataset tarball and companion MD5 file into the specified
        controller directory. The controller directory and links will be
        created if necessary.

        Args:
            controller: associated controller name
            tarfile: dataset tarball path

        Returns
            Tarball object
        """
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
        self.tarballs[tarball.name] = tarball
        self.datasets[tarball.resource_id] = tarball
        return tarball

    def unpack(self, dataset_id: str):
        """
        Unpack a tarball into the INCOMING tree, creating the INCOMING
        controller directory if necessary.

        Args:
            dataset_id: Dataset resource ID
        """
        tarball = self.find_dataset(dataset_id)
        tarball.controller.unpack(dataset_id)

    def uncache(self, dataset_id: str):
        """
        Remove the unpacked INCOMING tree.

        Args:
            dataset_id: Dataset resource ID to "uncache"
        """
        tarball = self.find_dataset(dataset_id)
        controller = tarball.controller
        controller.uncache(dataset_id)
        self._clean_empties(controller.name)

    def delete(self, dataset_id: str):
        """
        Delete the tarball and MD5 file as well as all unpacked artifacts.

        Args:
            dataset_id: Dataset resource ID to delete
        """
        tarball = self.find_dataset(dataset_id)
        name = tarball.name
        tarball.controller.delete(dataset_id)
        del self.datasets[dataset_id]
        del self.tarballs[name]
        self._clean_empties(tarball.controller_name)
