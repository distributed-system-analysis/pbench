from logging import Logger
from pathlib import Path
import re
import selinux
import shutil
from typing import Dict, List, Union

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

    def __init__(self, path: Union[str, Path]):
        self.path = str(path)

    def __str__(self) -> str:
        return f"The file path {self.path!r} is not a tarball"


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


class Tarball:
    """
    This class corresponds to the physical representation of a Dataset: the
    tarball, the MD5 file, and the unpacked data.

    It provides discovery and management methods related to a specific
    dataset.
    """

    TARBALL_SUFFIX = ".tar.xz"

    @staticmethod
    def is_tarball(path: Union[Path, str]) -> bool:
        """
        Determine whether a path has the expected suffix to qualify as a Pbench
        tarball.

        Args:
            path: file path

        Returns:
            True if path ends with the supported suffix, False if not
        """
        return str(path).endswith(Tarball.TARBALL_SUFFIX)

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

        Raises:
            BadFilename: the path name does not end in ".tar.xz"

        Returns:
            The stripped "stem" of the dataset
        """
        if Tarball.is_tarball(path):
            return path.name[: -len(Tarball.TARBALL_SUFFIX)]
        else:
            raise BadFilename(path)

    def __init__(self, path: Path, controller: "Controller"):
        """
        Construct a `Tarball` object instance representing a tarball found on
        disk.

        Args:
            path: The file path to a discovered tarball (.tar.xz file) in the
                configured ARCHIVE directory for a controller.
            controller: The associated Controller object
        """
        self.name = self.stem(path)
        self.controller = controller
        self.logger = controller.logger
        self.tarball_path = path
        self.unpacked: Path = None
        self.results_link: Path = None
        self.md5_path = path.with_suffix(".xz.md5")
        self.controller_name = controller.name

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

    @staticmethod
    def create(tarball: Path, controller: "Controller") -> "Tarball":
        """
        This is an alternate constructor to move an incoming tarball into the
        proper place along with the md5 companion file. It returns the new
        Tarball object.
        """

        # Validate the tarball suffix and extract the dataset name
        name = Tarball.stem(tarball)

        # NOTE: with_suffix replaces only the final suffix, .xz, not the full
        # standard .tar.xz
        md5_source = tarball.with_suffix(".xz.md5")

        # If either expected destination file exists, something is wrong
        if (controller.path / tarball.name).exists():
            raise DuplicateDataset(name)
        if (controller.path / md5_source.name).exists():
            raise DuplicateDataset(name)

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

        return Tarball(destination, controller)

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
        Determine whether the path's name matches a known state directory
        pattern. Most of the standard Pbench state directories are fixed
        strings, but `WONT-INDEX` can be suffixed with ".n" where "n" is
        a pbench_index error exit code.

        Args:
            directory: A directory path

        Returns:
            True if the path's name matches a state directory pattern
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
        self.state_dirs: Dict[str, Path] = {}
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
            if Controller.is_statedir(file):
                self.state_dirs[file.name] = file
            elif file.is_file() and file.name[-7:] == ".tar.xz":
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
                    self.tarballs[dataset].record_results(file)

    @staticmethod
    def create(name: str, options: PbenchServerConfig, logger: Logger) -> "Controller":
        """
        Create a new controller directory under the ARCHIVE tree if one doesn't
        already exist, and return a Controller object.

        Returns:
            Controller object
        """
        controller_dir = options.ARCHIVE / name
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

        NOTE: This does not not preserve the 0.69 --prefix and --user behaviors
        which alter the RESULTS tree directory structure and maintain an
        additional USERS tree; these are not useful or desirable for 0.72 with
        real users and metadata support.

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
        tarball.uncache()
        self.delete_if_empty(self.results)
        self.delete_if_empty(self.incoming)

    def delete(self, dataset: str):
        """
        Delete a dataset and remove it from the controller. This will also
        remove any links to the dataset tarball from the controller's state
        directories.

        Args:
            dataset: Name of dataset to delete
        """
        tarball = self.tarballs[dataset]
        for file in self.path.iterdir():
            if Controller.is_statedir(file):
                for link in file.iterdir():
                    if link.samefile(tarball.tarball_path):
                        link.unlink()
        tarball.delete()
        del self.tarballs[dataset]


class FileTree:
    """
    A hierarchical representation of the Pbench on-disk file structure.

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
        a dataset. Within each controller you'll find:

            A set of "dataset" files, each comprising a `.tar.xz` tarball and a
            `.tar.xz.md5` MD5 file.

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
                for each tarball in the controller.)

    INCOMING

        The INCOMING tree is rooted under the Pbench "top dir" public_html
        directory, conventionally something like

            /srv/pbench/public_html/incoming/

        It's also linked from /var/www/html/incoming.

        Like the ARCHIVE tree, it will contain a directory for each controller;
        however each controller will have a subdirectory for each tarball, with
        the root name of the tarball (without the trailing `.tar.xz`), which
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

    NOTE: this overview is specific to Pbench 0.72. While the descriptions here
    are mostly applicable to 0.69 as well, there are additional complications
    (and another root directory tree) we're dropping for 0.72, including the
    entire USERS tree, which is replaced by real user ownership, and a "prefix"
    mechanism that allowed tarballs to be nested within an arbitrary directory
    hierarchy under the RESULTS controller directory.
    """

    # The FileTree class owns the definition of the "controller" level
    # directory where PUT will store uploading files. Co-locating this
    # with the ARCHIVE tree ensures that we can move files without an
    # additional copy, and the upload will already fail if the file
    # system has insufficient space. Defining the directory here allows
    # FileTree discovery to ignore it.
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
        self.options = options
        self.archive_root = self.options.ARCHIVE
        self.incoming_root = self.options.INCOMING
        self.results_root = self.options.RESULTS
        self.logger = logger
        self.controllers: Dict[str, Controller] = {}
        self.datasets: Dict[str, Tarball] = {}

    def full_discovery(self):
        """
        We discover the ARCHIVE, INCOMING, and RESULTS trees as defined by the
        pbench-server.cfg file.

        Full discovery is not required before adding or deleting a dataset.
        """
        self._discover_archive()
        self._discover_unpacked()
        self._discover_results()

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
            raise DatasetNotFound(dataset) from None

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
        if archive.exists() and not any(archive.glob("*.tar.xz")):
            for file in archive.iterdir():
                if Controller.is_statedir(file):
                    if not any(file.iterdir()):
                        file.rmdir()
            if not any(archive.iterdir()):
                archive.rmdir()
            del self.controllers[controller]

    def _add_controller(self, directory: Path) -> None:
        """
        Create a new Controller object, add it to the set of known controllers,
        and append the discovered datasets (tarballs) to the list of known
        datasets.

        Args:
            directory: A controller directory within the ARCHIVE tree
        """
        controller = Controller(
            directory, self.options.INCOMING, self.options.RESULTS, self.logger
        )
        self.controllers[controller.name] = controller
        self.datasets.update(controller.tarballs)

    def _discover_archive(self):
        """
        Build a representation of the ARCHIVE tree, recording controllers (top
        level directories), the tarballs and MD5 files that represent datasets,
        and the server chain "state" directories.
        """
        for file in self.archive_root.iterdir():
            if file.is_dir() and file.name != FileTree.TEMPORARY:
                self._add_controller(file)

    def _discover_unpacked(self):
        """
        Build a representation of the "INCOMING" unpacked dataset tree,
        recording controllers (top level directories), the unpacked trees that
        represent datasets, and the expected links back to the ARCHIVE tree.
        """
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
            A Tarball object representing the dataset that was found.
        """
        if dataset in self.datasets:
            return self.datasets[dataset]

        # The dataset isn't already known; so search for it in the ARCHIVE tree
        # and (if found) discover the controller containing that dataset.
        for dir in self.archive_root.iterdir():
            if dir.is_dir():
                for file in dir.glob("*.tar.xz"):
                    name = Tarball.stem(file)
                    if name == dataset:
                        self._add_controller(dir)
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
        if not dataset.is_file():
            raise BadFilename(dataset)
        name = Tarball.stem(dataset)
        if name in self.datasets:
            raise DuplicateDataset(name)
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
