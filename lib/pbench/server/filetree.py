from logging import Logger
from pathlib import Path
import re
import selinux
import shutil
from typing import Dict, List

from pbench.server import PbenchServerConfig
from pbench.server.database.models.datasets import Dataset


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

    def __init__(self, path: str):
        self.path = str(path)

    def __str__(self) -> str:
        return f"The file path {self.path} is not a tarball"


class DatasetNotFound(FiletreeError):
    """
    The on-disk representation of a dataset (tarball and MD5 companion) were
    not found in the ARCHIVE tree.
    """

    def __init__(self, dataset: str):
        self.dataset = dataset

    def __str__(self) -> str:
        return f"The dataset named {self.dataset!r} is not present in the file tree"


class DuplicateDataset(FiletreeError):
    """
    A duplicate dataset name was detected.
    """

    def __init__(self, dataset: str):
        self.dataset = dataset

    def __str__(self) -> str:
        return f"A dataset named {self.dataset!r} is already present in the file tree"


class ControllerNotFound(FiletreeError):
    """
    A specified controller name does not exist in the ARCHIVE tree.
    """

    def __init__(self, controller: str):
        self.controller = controller

    def __str__(self) -> str:
        return (
            f"The controller name {self.controller!r} is not present in the file tree"
        )


class Tarball:
    """
    This class corresponds to the physical representation of a Dataset: the
    tarball, the MD5 file, and the unpacked data.

    It provides discovery and management methods related to a specific
    dataset.
    """

    @staticmethod
    def stem(path: Path) -> str:
        """
        The Path.stem() removes a single suffix, so our standard "a.tar.xz"
        returns "a.tar" instead of "a". We could double-stem, but instead
        this just checks for the expected 7 character suffix and strips it.

        If the path does not end in ".tar.xz" then the full path.name is
        returned.

        Args:
            path: A file path that might be a Pbench tarball

        Returns:
            The stripped "stem" of the dataset
        """
        name = path.name
        return name[:-7] if name[-7:] == ".tar.xz" else name

    def __init__(self, path: Path, controller: "Controller"):
        """
        Construct a `Tarball` object instance representing a tarball found on
        disk.

        Args:
            path: The file path to a discovered tarball (.tar.xz file) in the
                configured ARCHIVE directory for a controller.
            controller: The associated Controller object
        """
        self.name = Tarball.stem(path)
        self.controller = controller
        self.logger = controller.logger
        self.tarball_path = path
        self.unpacked: Path = None
        self.results_link: Path = None
        self.md5_path = path.with_suffix(".xz.md5")
        self.controller_name = path.parent.name

    def record_unpacked(self, directory: Path):
        """
        Record that an unpacked tarball directory was found for this dataset.

        Args:
            directory: The unpacked INCOMING tree directory for the dataset
        """
        self.unpacked = directory

    def record_results(self, link: Path):
        """
        Record that a results directory link was found for this dataset.

        Args:
            link: The symlink in the results tree to the incoming directory
        """
        self.results_link = link

    # Most of the "operational" methods below this point should be coordinated
    # through Controller and/or FileTree methods, which are aware of higher
    # level file tree structure, including the parallel INCOMING and RESULTS
    # trees.
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

    @staticmethod
    def create(tarball: Path, controller: "Controller") -> "Tarball":
        """
        This is an alternate constructor to move an incoming tarball into the
        proper place along with the md5 companion file. It returns the new
        Tarball object.
        """
        destination = controller.path / tarball.name

        # NOTE: with_suffix replaces only the final suffix, .xz, not the full
        # standard .tar.xz
        md5_source = tarball.with_suffix(".xz.md5")
        md5_destination = controller.path / md5_source.name

        # Copy the MD5 file first; only if that succeeds, copy the tarball
        # itself.
        try:
            shutil.copy2(md5_source, md5_destination)
        except Exception as e:
            controller.logger.error("ERROR copying dataset {} MD5: {}", tarball, e)
            raise

        try:
            moved = shutil.copy2(tarball, destination)
        except Exception as e:
            try:
                md5_destination.unlink()
            except Exception as e:
                controller.logger.error(
                    "Unable to recover by removing MD5 after tarball copy failure: {}",
                    e,
                )
            controller.logger.error("ERROR copying dataset {}: {}", tarball, e)
            raise

        # Restore the SELinux context properly
        try:
            selinux.restorecon(destination)
            selinux.restorecon(md5_destination)
        except Exception as e:
            # log it but do not abort
            controller.logger.error("Unable to 'restorecon {}', {}", destination, e)

        # To get the new tarball into the server pipeline, we start with a
        # symlink in the TODO state directory.
        try:
            controller.link(destination, "TODO")
        except Exception as e:
            controller.logger.error(
                "Failed to link dataset {} into TODO state directory: {}",
                destination,
                e,
            )

        # If we were able to copy both files, remove the originals
        try:
            tarball.unlink()
            md5_source.unlink()
        except Exception as e:
            controller.logger.error(
                "WARNING removing incoming dataset {}: {}", tarball, e
            )

        return Tarball(moved, controller)

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
        unpacked.mkdir()  # Just create an empty directory for now
        self.unpacked = unpacked
        results_link = results / self.name
        results_link.symlink_to(unpacked)
        self.results_link = results_link

    def uncache(self):
        """
        Remove the unpacked tarball directory and all contents. The Tarball
        object isn't directly aware of the RESULTS tree at all, so the caller
        is responsible for managing that along with the controller directories
        in each tree.
        """
        if self.unpacked:
            try:
                shutil.rmtree(self.unpacked)
                self.unpacked = None
            except Exception as e:
                self.logger.error("{}", e)
        if self.results_link:
            try:
                self.results_link.unlink()
                self.results_link = None
            except Exception as e:
                self.logger.error("{}", e)

    def delete(self):
        """
        Delete the tarball and MD5 file
        """
        self.uncache()
        if self.md5_path:
            # NOTE: it's actually an error if there's no MD5 companion, but
            # since Tarball object creation is driven by presence of the
            # .tar.xz file we won't assume it's there to delete.
            self.md5_path.unlink()
            self.md5_path = None
        self.tarball_path.unlink()
        self.tarball_path = None


class Controller:
    """
    Record the existence of a "controller" in the file store: this simply means
    a directory that was found within the root ARCHIVE directory. A controller
    with no data may be ignored in most contexts, but will trigger an audit.
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
    def is_statedir(directory: Path) -> bool:
        """
        Determine whether the path's name matches a known state directory
        pattern. Most of the standard Pbench state directories are fixed
        strings, but `WONT-INDEX` can be suffixed with ".n" where "n" is
        a pbench_index error exit code.

        Args:
            directory: A directory path

        Returns:
            True if the path's name matches a state directory pattern
        """
        name = directory.name
        for state in Controller.STATE_DIRS:
            if re.fullmatch(state, name):
                return True
        return False

    def __init__(self, path: Path, incoming: Path, results: Path, logger: Logger):
        """
        Manage the representation of a controller on disk, which is a set of
        directories; one each in the ARCHIVE, INCOMING, and RESULTS tree.

        Args:
            path: Controller directory path
            incoming: The root of the INCOMING tree
            results: The root of the RESULTS tree
            logger: Logger object
        """
        self.logger = logger
        self.name = path.name
        self.path = path
        self.errors: List[str] = []
        self.state_dirs = {}
        self.tarballs: Dict[str, Tarball] = {}
        self.incoming: Path = incoming / self.name
        self.results: Path = results / self.name
        self._discover_tarballs()

    def _discover_tarballs(self):
        """
        Discover the tarballs and state directories within the ARCHIVE tree's
        controller directory.
        """
        for file in self.path.iterdir():
            if file.is_dir():
                if Controller.is_statedir(file):
                    self.state_dirs[file.name] = file
            elif file.name[-7:] == ".tar.xz":
                tarball = Tarball(file, self)
                self.tarballs[tarball.name] = tarball

    def check_incoming(self):
        """
        Discover whether the INCOMING directory tree has an unpacked copy of
        the dataset's tarball.
        """
        for file in self.incoming.iterdir():
            if file.is_dir():
                dataset = file.name
                if dataset in self.tarballs:
                    self.tarballs[dataset].record_unpacked(file)

    def check_results(self):
        """
        Discover whether the RESULTS directory tree has a link to the unpacked
        INCOMING directory.
        """
        for file in self.results.iterdir():
            if file.is_symlink():
                dataset = file.name
                if dataset in self.tarballs:
                    tarball = self.tarballs[dataset]
                    tarball.record_results(file)

    @staticmethod
    def create(name: str, options: PbenchServerConfig, logger: Logger) -> "Controller":
        """
        Create a new controller directory under the ARCHIVE tree if one doesn't
        already exist, and return a Controller object.

        Returns:
            Controller object
        """
        controller_dir = options.ARCHIVE / name
        if not controller_dir.exists():
            controller_dir.mkdir(exist_ok=True, mode=0o755)
        (controller_dir / "TODO").mkdir(exist_ok=True)
        return Controller(controller_dir, options.INCOMING, options.RESULTS, logger)

    def create_tarball(self, dataset: Path) -> Tarball:
        """
        Create a new dataset under the controller, link it to the controller,
        and return the new Tarball object.

        Args:
            dataset: Path to source tarball file

        Returns:
            Tarball object
        """
        tarball = Tarball.create(dataset, self)
        self.tarballs[tarball.name] = tarball
        return tarball

    def link(self, dataset: Path, state: str):
        """
        Create a state link within the controller sub-tree.

        Args:
            dataset: Tarball path
            state: State directory name (e.g., "TODO")
        """
        (self.state_dirs[state] / dataset.name).symlink_to(dataset)

    def unpack(self, dataset: str):
        """
        Unpack a tarball into the INCOMING tree. Create the INCOMING controller
        directory if necessary, along with the RESULTS tree link.

        NOTE: This does not look at tarball metadata.log, and therefore cannot
        consider the `prefix` and `user` metadata which, in 0.69, affect
        (respectively) the directory path of the RESULTS tree link, and whether
        an entry is added under a different USERS tree. It's unclear we want
        to preserve either behavior for 0.72 (especially USERS, which we've
        replaced with true users and ownership).

        Args:
            dataset: Name of the dataset to unpack
        """
        tarball = self.tarballs[dataset]
        self.incoming.mkdir(exist_ok=True)
        self.results.mkdir(exist_ok=True)
        tarball.unpack(self.incoming, self.results)

    def uncache(self, dataset: str):
        """
        The reverse of `unpack`, removing the RESULTS tree link and the
        unpacked tarball contents from INCOMING.

        Args:
            dataset: Name of dataset to remove
        """
        tarball = self.tarballs[dataset]
        results_link = self.results / tarball.name
        if results_link.exists():
            results_link.unlink()
        if self.results.exists() and not list(self.results.iterdir()):
            self.results.rmdir()
        incoming_dir = self.incoming / tarball.name
        if incoming_dir.is_dir():
            shutil.rmtree(incoming_dir, ignore_errors=True)
        if self.incoming.exists() and not list(self.incoming.iterdir()):
            self.incoming.rmdir()

    def delete(self, dataset: str):
        """
        Delete a dataset and remove it from the controller. This will also
        remove any links to the dataset tarball from the controller's state
        directories.

        NOTE: This relies on FileTree.delete() having already called the
        controller uncache; we can't completely clean up within the controller
        scope.

        Args:
            dataset: Name of dataset to delete
        """
        self.logger.info("LOOKING for {} in {}", dataset, self.tarballs)
        tarball = self.tarballs[dataset]
        for file in self.path.iterdir():
            if file.is_dir() and Controller.is_statedir(file):
                for link in file.iterdir():
                    if link.samefile(tarball.tarball_path):
                        link.unlink()
        tarball.delete()
        del self.tarballs[dataset]


class FileTree:
    """
    A hierarchical representation of the Pbench on-disk file structure,
    including the ARCHIVE, INCOMING, and RESULTS directory subtrees.
    """

    # The FileTree class owns the definition of the "controller" level
    # directory where PUT will store uploading files. Co-locating this
    # with the ARCHIVE tree ensures that we can move files without an
    # additional copy, and the upload will already fail if the file
    # system has insufficient space. Defining the directory here allows
    # FileTree discovery to ignore it.
    TEMPORARY = "UPLOAD"

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
        self.options = options
        self.archive_root = self.options.ARCHIVE
        self.incoming_root = self.options.INCOMING
        self.results_root = self.options.RESULTS
        self.logger = logger
        self.controllers: Dict[str, Controller] = {}
        self.datasets: Dict[str, Tarball] = {}

    def full_discovery(self):
        """
        Discover and diagnose the state of the entire file tree, including the
        ARCHIVE, INCOMING, and RESULTS subtrees.

        This is useful for standalone reporting, including to enable an audit
        check. Generally it's overkill for specific operations such as adding
        or removing a dataset. This setup is sufficient but not necessary for
        mutation operations.
        """
        self._discover_filesystem()

    def __contains__(self, dataset: str) -> bool:
        """
        Allow asking whether a FileTree contains an entry for a specific
        dataset.

        Args:
            dataset: Dataset name

        Returns:
            True if the dataset is present
        """
        return dataset in self.datasets

    def __getitem__(self, dataset: str) -> Dataset:
        """
        Direct access to a dataset Tarball object by name.

        Args:
            dataset: Dataset name

        Returns:
            Tarball object
        """
        try:
            return self.datasets[dataset]
        except KeyError:
            raise DatasetNotFound(dataset)

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
        if results.exists() and not list(results.iterdir()):
            results.rmdir()
        incoming = self.options.INCOMING / controller
        if incoming.exists() and not list(incoming.iterdir()):
            incoming.rmdir()
        archive = self.options.ARCHIVE / controller
        if archive.exists() and not list(archive.glob("*.tar.xz")):
            for file in archive.iterdir():
                if file.is_dir() and Controller.is_statedir(file):
                    if not list(file.iterdir()):
                        file.rmdir()
            if not list(archive.iterdir()):
                archive.rmdir()
            del self.controllers[controller]

    def _discover_filesystem(self):
        """
        Update the FileTree object with the structure of the Pbench server file
        tree representation.

        We discover the ARCHIVE, INCOMING, and RESULTS trees as defined by the
        pbench-server.cfg file. We do not support the 0.69 USERS directory,
        which is completely superseded by dataset user ownership in 0.72. We
        also do not support the `prefix` mechanism that allowed inserting a
        directory prefix or directory sub-tree in front of the RESULTS link
        which exposes the unpacked tarball data. Both of these may become
        accessible through dataset metadata.
        """
        self._discover_archive()
        self._discover_unpacked()
        self._discover_results()

    def _discover_archive(self):
        """
        Build a representation of the ARCHIVE tree, recording controllers (top
        level directories), the tarballs and MD5 files that represent datasets,
        and the server chain "state" directories.
        """
        if not self.archive_root.exists():
            return
        for file in self.archive_root.iterdir():
            if file.is_dir() and file.name != FileTree.TEMPORARY:
                controller = Controller(
                    file, self.options.INCOMING, self.options.RESULTS, self.logger
                )
                self.controllers[controller.name] = controller
                self.datasets.update(controller.tarballs)

    def _discover_unpacked(self):
        """
        Build a representation of the "INCOMING" unpacked dataset tree,
        recording controllers (top level directories), the unpacked trees that
        represent datasets, and the expected links back to the ARCHIVE tree.
        """
        if not self.incoming_root.exists():
            return
        for file in self.incoming_root.iterdir():
            if file.is_dir():
                name = file.name
                if name in self.controllers:
                    self.controllers[name].check_incoming()

    def _discover_results(self):
        """
        Build a representation of the "RESULTS" dataset tree, recording the
        controllers (top level directories), and the expected links back into
        the INCOMING tree.

        NOTE: subclass and remove for block store? I don't think this has any
        real meaning in our block store model...
        """
        if not self.results_root.exists():
            return
        for file in self.results_root.iterdir():
            if file.is_dir():
                name = file.name
                if name in self.controllers:
                    self.controllers[name].check_results()

    def find_dataset(self, dataset: str) -> Tarball:
        """
        Given the name of a dataset, search the ARCHIVE tree for a controller
        with that dataset name. This will build the Controller and Tarball
        object for that dataset if they do not already exist.

        FIXME: This builds the entire Controller, which will discover all
        datasets within the controller. This could be streamlined... however
        for create and delete, we need to know the state link directories.

        This allows a targeted minimal entry for mutation without discovering
        the entire tree.

        Args:
            dataset: The name of a dataset that might exist somewhere in the
                file tree

        Raises:
            DatasetNotFound: the ARCHIVE tree does not contain a tarball that
                corresponds to the dataset name

        Returns:
            Either None if the dataset is not found or the Tarball object
            representing the dataset that was found.
        """
        if dataset in self.datasets:
            return self.datasets[dataset]

        # If we haven't already discovered the dataset, search for it, and
        # discover just the controller containing that dataset name.
        for dir in self.archive_root.iterdir():
            self.logger.info("Checking controller {}", str(dir))
            if dir.is_dir():
                for file in dir.glob("*.tar.xz"):
                    name = Tarball.stem(file)
                    self.logger.info("Checking tarball {} [{}]", str(file), name)
                    if name == dataset:
                        controller = Controller(
                            dir,
                            self.options.INCOMING,
                            self.options.RESULTS,
                            self.logger,
                        )
                        self.controllers[controller.name] = controller
                        self.datasets.update(controller.tarballs)
                        return self.datasets[dataset]
        raise DatasetNotFound(dataset)

    # These are wrappers for controller and tarball operations which need to be
    # aware of higher-level constructs in the Pbench artifact tree such as the
    # ARCHIVE, INCOMING, and RESULTS directory branches. These will manage that
    # higher level environment surrounding the encapsulated class methods.
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

    def create(self, controller_name: str, dataset: Path) -> Tarball:
        """
        Move a dataset tarball and companion MD5 file into the specified
        controller directory. The controller directory and links will be
        created if necessary.

        Args:
            controller: associated controller name
            dataset: dataset tarball path

        Returns
            Tarball object
        """
        if dataset in self.datasets:
            raise DuplicateDataset(dataset)
        if controller_name in self.controllers:
            controller = self.controllers[controller_name]
        else:
            controller = Controller.create(controller_name, self.options, self.logger)
            self.controllers[controller_name] = controller
        tarball = controller.create_tarball(dataset)
        self.datasets[tarball.name] = tarball
        return tarball

    def unpack(self, dataset: str):
        """
        Unpack a tarball into the INCOMING tree, creating the INCOMING
        controller directory if necessary.
        """
        tarball = self.find_dataset(dataset)
        tarball.controller.unpack(dataset)

    def uncache(self, dataset: str):
        """
        Remove the unpacked INCOMING tree.

        Args:
            dataset: Dataset name to "uncache"
        """
        tarball = self.find_dataset(dataset)
        controller = tarball.controller
        controller.uncache(dataset)
        self._clean_empties(controller.name)

    def delete(self, dataset: str):
        """
        Delete the tarball and MD5 file as well as all unpacked artifacts

        Args:
            dataset: Dataset name to delete
        """
        tarball = self.find_dataset(dataset)
        tarball.controller.delete(dataset)
        del self.datasets[dataset]
        self._clean_empties(tarball.controller_name)
