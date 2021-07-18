#! /usr/bin/env python3
# -*- mode: python -*-
import os
import sys
import glob
import tempfile

from pathlib import Path
from typing import Callable, IO, List, Union

from configparser import ConfigParser
from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.hierarchy import (
    Hierarchy,
    ArchiveHierarchy,
    ControllerHierarchy,
    IncomingHierarchy,
    ResultsHierarchy,
    UserHierarchy,
)
from pbench.server.report import Report


_NAME_ = "pbench-audit-server"


class PbenchMDLogConfig(ConfigParser):
    """A ConfigParser object for a specific config file (or list of files)."""

    def __init__(self, cfg_name: Union[str, List]) -> None:
        super().__init__()
        self.read(cfg_name)


def verify_valid_controllers(hier: Hierarchy, controllers: List) -> None:
    """Find all the controllers and check whether they are directory"""
    for controller_path in controllers:
        if controller_path.is_dir():
            hier.add_controller(controller_path.name)
        else:
            hier.add_bad_controller(controller_path)


def verify_subdirs(hier, controller: List, directories: List) -> None:
    linkdirs = sorted(hier.config.LINKDIRS.split(" "))
    if directories:
        for dirent in directories:
            if (
                not dirent.startswith("WONT-INDEX")
                and dirent != "_QUARANTINED"
                and dirent not in linkdirs
                and Path(hier.path, controller, dirent).exists()
            ):
                hier.add_unexpected_entries(
                    Hierarchy.UNEXPECTED_DIRS, controller, dirent
                )
    else:
        hier.add_unexpected_entries(
            Hierarchy.SUBDIR_STATUS_INDICATORS, controller, hier.SUBDIR
        )


def verify_prefixes(hier: ArchiveHierarchy, controller: List) -> None:
    prefix_dir = Path(hier.path, controller, ".prefix")
    if not prefix_dir.exists():
        return
    if not prefix_dir.is_dir():
        hier.add_unexpected_entries(
            Hierarchy.PREFIX_STATUS_INDICATORS, controller, hier.PREFIX_DIR
        )
        return

    prefixes = prefix_dir.glob("*")

    for prefix_path in prefixes:
        if prefix_path.name.startswith("prefix."):
            hier.add_unexpected_entries(
                Hierarchy.WRONG_PREFIXES, controller, prefix_path.name
            )
        elif not prefix_path.name.endswith(".prefix"):
            hier.add_unexpected_entries(
                Hierarchy.NON_PREFIXES, controller, prefix_path.name
            )


def verify_archive(hier: ArchiveHierarchy) -> None:
    """Scans through Archive Hierarchy
        For each "good" controller do:
            - Verify the tarballs for symlinks
            - Verify all files are *.tar.xz[.md5] flagging
                *.tar.xz.prefix or prefix.*.tar.xz in the
                controller directory
            - Verify all sub-directories of a given controller are one
                of the expected state directories
            - Verify all prefix files in .prefix directories are *.prefix

    Args
        hier -- Archive Herarchy object

    """
    controllers = Path(hier.path).glob("*")
    verify_valid_controllers(hier, controllers)

    # Check "good" controller and get the tarballs it contains
    for controller in hier.controllers:
        direct_entries = glob.iglob(os.path.join(hier.path, controller, "*"))
        hidden_entries = Path(hier.path, controller).glob(".*")
        if hidden_entries:
            for hid_entries_path in hidden_entries:
                if hid_entries_path.is_file():
                    hier.add_unexpected_entries(
                        Hierarchy.UNEXPECTED_OBJECTS, controller, hid_entries_path.name,
                    )
        controller_subdir = list()
        for item in direct_entries:
            item_path = Path(item)
            if item_path.is_dir():
                controller_subdir.append(item_path.name)
            elif item_path.is_symlink():
                try:
                    item_p = item_path.resolve(strict=True)
                except FileNotFoundError:
                    hier.add_error_or_inconceivable_entries(
                        Hierarchy.ERROR,
                        controller,
                        f"{item_path.name} path, '{item_path}', does not resolve to a real location",
                    )
                symlink_item = f"{item_path.name} -> {item_p}"
                hier.add_unexpected_entries(
                    Hierarchy.UNEXPECTED_SYMLINKS, controller, symlink_item
                )
            elif item_path.is_file():
                if item_path.name.endswith(".tar.xz") or item_path.name.endswith(
                    ".tar.xz.md5"
                ):
                    hier.add_tarballs(controller)
                else:
                    hier.add_unexpected_entries(
                        Hierarchy.UNEXPECTED_OBJECTS, controller, item_path.name
                    )
            else:
                hier.add_error_or_inconceivable_entries(
                    Hierarchy.INCONCEIVABLE, controller, item_path.name,
                )
        verify_subdirs(hier, controller, controller_subdir)
        verify_prefixes(hier, controller)


def verify_tar_dirs(
    ihier: IncomingHierarchy,
    tarball_list: List,
    add_unexpected_entries: Callable[[str, str, str], None],
    controller: str,
) -> None:
    """Verifies tarball directory and checks whether it is accessible

    Args
        ihier -- Incoming Hierarchy Object
        tarball_list -- list of tarball names
        add_unexpected_entries -- function to add unexpected entries
        controller -- the name of the controller to be associated with the
                        tar ball

    """
    for tb in tarball_list:
        if tb.endswith(".unpack"):
            tar = tb[:-7]
            tar = tar + ".tar.xz"
            dict_val = Hierarchy.INVALID_UNPACKING_DIRS
        else:
            tar = tb + ".tar.xz"
            dict_val = Hierarchy.INVALID_TB_DIRS
        tarfile = Path(ihier.config.ARCHIVE, controller, tar)
        if not os.access(tarfile, os.R_OK):
            add_unexpected_entries(dict_val, controller, tb)


def verify_incoming(ihier: IncomingHierarchy, verifylist: List) -> None:
    """Review Incoming Hierarchy
        - Flag expanded tar ball directories that don't exist in "ARCHIVE"
        - Flag empty tar ball directories
        - Flag invalid tar ball links
        - Flag tar ball links pointing to an invalid unpack directory
        - Flag tar ball links/directories which don't have a tar ball
            in the "ARCHIVE" hierarchy

    Args
        ihier -- Incoming Herarchy object

    """
    for controller in verifylist:
        ihier.add_controller(controller)

        if not Path(ihier.config.ARCHIVE, controller).is_dir():
            # Skip incoming controller directories that don't have an $ARCHIVE
            # directory, handled in another part of the audit.
            continue

        tarball_dirs = list()
        unpacking_tarball_dirs = list()

        for dir_path in Path(ihier.config.INCOMING, controller).iterdir():
            if dir_path.is_dir():
                if list(dir_path.iterdir()):
                    tarball_dirs.append(dir_path.name)
                elif dir_path.name.endswith(".unpack"):
                    unpacking_tarball_dirs.append(dir_path.name)
                else:
                    ihier.add_unexpected_entries(
                        Hierarchy.EMPTY_TARBALL_DIRS, controller, dir_path.name
                    )
            elif dir_path.is_symlink():
                ihier.add_unexpected_entries(
                    Hierarchy.TARBALL_LINKS, controller, dir_path.name
                )
            else:
                ihier.add_error_or_inconceivable_entries(
                    Hierarchy.INCONCEIVABLE, controller, dir_path.name,
                )

        verify_tar_dirs(ihier, tarball_dirs, ihier.add_unexpected_entries, controller)
        verify_tar_dirs(
            ihier, unpacking_tarball_dirs, ihier.add_unexpected_entries, controller,
        )


def verify_prefix_hierarchy(
    rhier: ResultsHierarchy, controller: str, prefix: str, prefix_file: Path, path: Path
):
    """Args-

        rhier -- Results Hierarchy Object
        controller -- the name of the controller associated with the
                        tar ball
        prefix -- extracted from config file associated with the tar ball
        prefix_file -- file name ending with .prefix suffix
        path -- path of the tar ball after controller
    """
    prefix_path = str(path.parent)
    if prefix_path == ".":
        if prefix:
            rhier.add_unexpected_entries(Hierarchy.BAD_PREFIXES, controller, path)
        elif prefix_file.exists():
            rhier.add_unexpected_entries(
                Hierarchy.UNUSED_PREFIX_FILES, controller, path
            )
    elif prefix:
        if prefix != prefix_path:
            rhier.add_unexpected_entries(Hierarchy.BAD_PREFIXES, controller, path)
    elif not prefix_file.exists():
        rhier.add_unexpected_entries(Hierarchy.MISSING_PREFIX_FILES, controller, path)
    else:
        try:
            prefix = prefix_file.read_text().replace("\n", "")
        except Exception:
            rhier.add_unexpected_entries(Hierarchy.BAD_PREFIX_FILES, controller, path)
        else:
            if prefix != prefix_path:
                rhier.add_unexpected_entries(Hierarchy.BAD_PREFIXES, controller, path)


def verify_user_arg(
    rhier: ResultsHierarchy, mdlogcfg: PbenchServerConfig, controller: str, path: Path
) -> None:
    """fetch user from the config file and verify its validity"""

    if rhier.path.parent == rhier.config.USERS:
        user_arg = rhier.path.name
        user = ""
        user = mdlogcfg.get("run", "user", fallback="")
        if user_arg != user:
            val = (
                Hierarchy.UNEXPECTED_USER_LINKS
                if not user
                else Hierarchy.WRONG_USER_LINKS
            )
            rhier.add_unexpected_entries(val, controller, path)


def path_below_controller(dir_path: Path, controller: str) -> Path:
    controller_path = os.path.join(controller, "")
    path = dir_path.split(controller_path, 1)[1]

    return Path(path)


def get_directory_entries(hierarchy: ResultsHierarchy, controller: str) -> Path:

    direct_entries = list()
    for root, dirs, files in os.walk(
        Path(hierarchy, controller), topdown=True, followlinks=False
    ):
        for name in files + dirs:
            direct_entries.append(Path(root, name))

    return direct_entries


def verify_results(rhier: ResultsHierarchy, verifylist: List):
    """Scans through Results Hierarchy and check the following:
        - Tar ball links that don't ultimately have a tar ball in "ARCHIVE"
        - Tar ball links that don't point to "INCOMING"
        - Tar ball links that exist in a prefix hierarchy but don't have a
            prefix file
        - Tar ball links that exist in a prefix hierarchy but have an invalid
            prefix file (can't read it)
        - Tar ball links that exist in a prefix hierarchy but don't match the
            stored prefix file prefix

    Args
        rhier -- Results Herarchy object
        verifylist -- list of verified controllers

    """
    for controller in verifylist:
        if not Path(rhier.config.ARCHIVE, controller).is_dir():
            # Skip incoming controller directories that don't have an archive
            # directory which is handled in another part of the audit.
            continue

        direct_entries = get_directory_entries(rhier.path, controller)
        rhier.add_controller(controller)

        for dir_path in direct_entries:
            path = path_below_controller(str(dir_path), controller)
            if dir_path.is_dir() and len(os.listdir(dir_path)) == 0:
                rhier.add_unexpected_entries(
                    Hierarchy.EMPTY_TARBALL_DIRS, controller, path
                )
            elif dir_path.is_symlink():
                link = os.path.realpath(str(dir_path))
                tb = path.name + ".tar.xz"
                incoming_path = Path(rhier.config.INCOMING, controller, dir_path.name)
                prefix_file = Path(
                    rhier.config.ARCHIVE,
                    controller,
                    ".prefix",
                    dir_path.name + ".prefix",
                )
                mdlogcfg = PbenchMDLogConfig(Path(incoming_path, "metadata.log"))
                prefix = mdlogcfg.get("run", "prefix", fallback="")
                if not Path(rhier.config.ARCHIVE, controller, tb).exists():
                    rhier.add_unexpected_entries(
                        Hierarchy.INVALID_TB_LINKS, controller, dir_path.name
                    )
                elif link != str(incoming_path):
                    rhier.add_unexpected_entries(
                        Hierarchy.INCORRECT_TB_DIR_LINKS, controller, dir_path.name
                    )
                elif not incoming_path.is_dir() and not incoming_path.is_symlink():
                    rhier.add_unexpected_entries(
                        Hierarchy.INVALID_TB_DIR_LINKS, controller, dir_path.name
                    )
                else:
                    verify_prefix_hierarchy(
                        rhier, controller, prefix, prefix_file, path
                    )

                verify_user_arg(rhier, mdlogcfg, controller, path)


def verify_controllers(hier: Hierarchy) -> None:
    """Controller Hierarchy:
        - Identify controllers that don't have a "ARCHIVE" directory
        - Identify empty controllers
        - Identify controllers that contain files and not directories or links

    Args
        hier -- Controller Hierarchy object

    """
    controllers = Path(hier.path).iterdir()
    verify_valid_controllers(hier, controllers)

    for controller in hier.controllers:
        dir_path = Path(hier.path, controller)
        if not Path(hier.config.ARCHIVE, controller).is_dir():
            # We have a controller in the hierarchy which does not have a
            # controller of the same name in the archive hierarchy.  All
            # lyzing it further.
            hier.add_controller_list(Hierarchy.MIALIST, Path(controller).name)
        else:
            # Report any controllers with objects other than directories
            # and links, while also recording any empty controllers.
            count_dir_entries = 0
            direct_entries = dir_path.glob("*")
            for item_path in direct_entries:
                count_dir_entries += 1
                if not item_path.is_dir() and not item_path.is_symlink():
                    hier.add_controller_list(
                        Hierarchy.UNEXPECTED_CONTROLLERS, controller
                    )
                    break
            else:
                if count_dir_entries == 0:
                    hier.add_controller_list(Hierarchy.EMPTY_CONTROLLERS, controller)
                    continue

            hier.add_verify_list(controller)


def verify_users(hier: UserHierarchy) -> None:
    """ Scans through Users Hierarchy:
        - Find "good' users
        - For each "good" user:
            - Review it just like a results hierarchy

    Args
        hier -- User Herarchy object

    """
    if not Path(hier.path).is_dir():
        print(
            f"The setting for USERS in the config file is {hier.path}, but that is"
            " not a directory"
        )
        return 1

    user_dirs = Path(hier.path).glob("*")

    for user_path in user_dirs:
        if user_path.is_dir():
            hier.add_user_dir(user_path)
        else:
            hier.add_unexpected_objects(user_path.name)


def check_and_dump(f: IO, hier: Hierarchy, ihier: Hierarchy) -> int:
    """ checks for 'if there is anything to report' in hierarchies and output
        the result of controller and incoming/results hierarchy

    Args
        f -- file object for writing results
        hier -- Controller Hierarchy object
        ihier -- Incoming/Results Hierarchy object

    """
    cnt = 0
    first_check = hier.check_controller()
    second_check = ihier.check_controller()
    if first_check or second_check:
        hier.header(f, "start", False)
        if first_check:
            cnt = hier.dump(f)
        if second_check:
            cnt = ihier.dump(f)
        hier.header(f, "end", True)
    return cnt


def check_directory_exists(pbdir_path: Path, pbdirname: str) -> bool:
    """checks for the existence of directories

        Args
            pbdir_path -- path of the directory
            pbdirname -- name of the directory

    """
    pbdir = Path(pbdir_path)
    try:
        pbdir_p = pbdir.resolve(strict=True)
    except FileNotFoundError:
        print(f"{_NAME_}: Bad {pbdirname}={pbdir}", file=sys.stderr)
        return False

    if not pbdir_p.is_dir():
        print(f"{_NAME_}: {pbdirname}={pbdir} is not a directory", file=sys.stderr)
        return False

    return True


def main():
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set '_PBENCH_SERVER_CONFIG' env variable",
            file=sys.stderr,
        )
        return 2

    try:
        config = PbenchServerConfig(cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e} (config file {cfg_name})", file=sys.stderr)
        return 1

    if not check_directory_exists(config.ARCHIVE, "ARCHIVE"):
        return 1

    if not check_directory_exists(config.INCOMING, "INCOMING"):
        return 1

    if not check_directory_exists(config.RESULTS, "RESULTS"):
        return 1

    if not check_directory_exists(config.USERS, "USERS"):
        return 1

    logger = get_pbench_logger(_NAME_, config)
    init_db(config, logger)

    ret = 0

    try:
        Path(config.LOGSDIR, "pbench-audit-server").mkdir()
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception as exc:
        print("Unable to create destination directory: ", exc)
        return 1
    logfile = Path(config.LOGSDIR, "pbench-audit-server", "pbench-audit-server.log")

    logger.info("start-{}", config.TS)

    with logfile.open(mode="w") as f:

        ahier = ArchiveHierarchy("archive", config.ARCHIVE, config)
        verify_archive(ahier)
        if ahier.check_controller():
            ahier.header(f, "start", False)
            ret = ahier.dump(f) or ret
            ahier.header(f, "end", True)

        ihier = IncomingHierarchy("Incoming", config.INCOMING, config)
        cihier = ControllerHierarchy("incoming", config.INCOMING, config)
        verify_controllers(cihier)
        verify_incoming(ihier, cihier.verifylist)
        ret = check_and_dump(f, cihier, ihier) or ret

        rhier = ResultsHierarchy("Results", config.RESULTS, config)
        crhier = ControllerHierarchy("results", config.RESULTS, config)
        verify_controllers(crhier)
        verify_results(rhier, crhier.verifylist)
        ret = check_and_dump(f, crhier, rhier) or ret

        uhier = UserHierarchy("users", config.USERS, config)
        verify_users(uhier)
        for user in uhier.users:
            verify_results(user, crhier.verifylist)
        if uhier.check_controller():
            uhier.header(f, "start", False)
            ret = uhier.dump(f) or ret
            uhier.header(f, "end", False)

    # prepare and send report
    with tempfile.NamedTemporaryFile(mode="w+t", dir=config.TMP) as reportfp:
        reportfp.write(
            f"{_NAME_}.run-{config.timestamp()}({config.PBENCH_ENV})\n{logfile.read_text()}"
        )
        reportfp.seek(0)
        report = Report(config, _NAME_)
        report.init_report_template()
        try:
            report.post_status(config.timestamp(), "status", reportfp.name)
        except Exception as exc:
            logger.warning("Report post Unsuccesful: '{}'", exc)

    return ret


if __name__ == "__main__":
    sts = main()
    sys.exit(sts)
