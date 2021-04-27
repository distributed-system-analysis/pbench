#! /usr/bin/env python3

import os
import sys
import glob
import tempfile

from pathlib import Path
from pbench.server import PbenchServerConfig
from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.server.report import Report
from configparser import ConfigParser, NoSectionError, NoOptionError
from pbench.server.hierarchy import (
    Hierarchy,
    ArchiveHierarchy,
    ControllerHierarchy,
    IncomingHierarchy,
    ResultsHierarchy,
    UserHierarchy,
)


_NAME_ = "pbench-audit-server"


class PbenchMDLogConfig(object):
    """A simple class to wrap a ConfigParser object in order to query a specific
    metadata.log file for a given tarball.
    """

    def __init__(self, cfg_name):
        self.conf = ConfigParser()
        self.files = self.conf.read([cfg_name])

    def get(self, *args, **kwargs):
        return self.conf.get(*args, **kwargs)


def verify_valid_controllers(hier, controllers):
    """Find all the non-directory files at the same level of the controller
    directories and report them, and find all the normal controller directories.
    """
    for controller_path in controllers:
        if controller_path.is_dir():
            hier.add_controller(controller_path.name)
        else:
            hier.add_bad_controller(controller_path)
    return 0


# Archive Hierarchy
def verify_subdirs(hier, controller, directories):
    linkdirs = sorted(hier.config.LINKDIRS.split(" "))
    if directories:
        for dirent in directories:
            if all(
                [
                    Path(hier.path, controller, dirent).exists(),
                    dirent != "_QUARANTINED",
                    not dirent.startswith("WONT-INDEX"),
                ]
            ):
                if dirent not in linkdirs:
                    hier.add_unexpected_entries(
                        Hierarchy.UNEXPECTED_DIRS, controller, dirent
                    )
    else:
        hier.add_unexpected_entries(
            Hierarchy.SUBDIR_STATUS_INDICATORS, controller, "subdirs"
        )

    return 0


def verify_prefixes(hier, controller):
    prefix_dir = Path(hier.path, controller, ".prefix")
    if not prefix_dir.exists():
        return 0
    if not prefix_dir.is_dir():
        hier.add_unexpected_entries(
            Hierarchy.PREFIX_STATUS_INDICATORS, controller, "prefix_dir"
        )
        return 1

    prefixes = prefix_dir.glob("*")

    for prefix_path in prefixes:
        if not prefix_path.name.startswith("prefix.") and not prefix_path.name.endswith(
            ".prefix"
        ):
            hier.add_unexpected_entries(
                Hierarchy.NON_PREFIXES, controller, prefix_path.name
            )
        elif prefix_path.name.startswith("prefix."):
            hier.add_unexpected_entries(
                Hierarchy.WRONG_PREFIXES, controller, prefix_path.name
            )

    return 0


# 'hier' is an object of ArchiveHierarchy class imported from hierarchy.py
def verify_archive(hier):

    controllers = Path(hier.path).glob("*")
    verify_valid_controllers(hier, controllers)

    # now check each "good" controller and get the tarballs it contains
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
                        f"{item_path.name}_path, '{item_path}', does not resolve to a real location",
                    )
                symlink_item = f"{item_path.name} -> {item_p}"
                hier.add_unexpected_entries(
                    Hierarchy.UNEXPECTED_SYMLINKS, controller, symlink_item
                )
            elif all(
                [
                    item_path.is_file(),
                    not item_path.name.endswith(".tar.xz"),
                    not item_path.name.endswith(".tar.xz.md5"),
                ]
            ):
                hier.add_unexpected_entries(
                    Hierarchy.UNEXPECTED_OBJECTS, controller, item_path.name
                )
            elif item_path.is_file() and (
                item_path.name.endswith(".tar.xz")
                or item_path.name.endswith(".tar.xz.md5")
            ):
                hier.add_tarballs(controller)
            else:
                hier.add_error_or_inconceivable_entries(
                    Hierarchy.INCONCEIVABLE, controller, item_path.name,
                )
        verify_subdirs(hier, controller, controller_subdir)
        verify_prefixes(hier, controller)

    return 0


# Incoming Hierarchy
def verify_tar_dirs(ihier, tarball_dirs, tblist, controller):
    for tb in tarball_dirs:
        if tb.endswith("unpack"):
            tar = tb[:-7]
            tar = f"{tar}.tar.xz"
            dict_val = Hierarchy.INVALID_UNPACKING_DIRS
        else:
            tar = f"{tb}.tar.xz"
            dict_val = Hierarchy.INVALID_TB_DIRS
        tarfile = Path(ihier.config.ARCHIVE, controller, tar)
        if tarfile.exists():
            if os.access(tarfile, os.R_OK):
                continue
        else:
            tblist(dict_val, controller, tb)
    return 0


# 'ihier' is IncomingHierarchy class object
def verify_incoming(ihier, verifylist):

    for controller in verifylist:
        ihier.add_controller(controller)

        if not Path(ihier.config.ARCHIVE, controller).is_dir():
            # Skip incoming controller directories that don't have an $ARCHIVE
            # directory, handled in another part of the audit.
            continue

        direct_entries = Path(ihier.config.INCOMING, controller).glob("*")
        tarball_dirs = list()
        unpacking_tarball_dirs = list()

        for dir_path in direct_entries:
            if dir_path.is_dir():
                if dir_path.name.endswith(".unpack"):
                    if len(os.listdir(dir_path)) == 0:
                        unpacking_tarball_dirs.append(dir_path.name)
                    else:
                        tarball_dirs.append(dir_path.name)
                else:
                    if len(os.listdir(dir_path)) == 0:
                        ihier.add_unexpected_entries(
                            Hierarchy.EMPTY_TARBALL_DIRS, controller, dir_path.name
                        )
                    else:
                        tarball_dirs.append(dir_path.name)
            elif dir_path.is_symlink():
                ihier.add_unexpected_entries(
                    Hierarchy.TARBALL_LINKS, controller, dir_path.name
                )
            else:
                ihier.add_error_or_inconceivable_entries(
                    Hierarchy.INCONCEIVABLE, controller, dir_path.name,
                )

        if tarball_dirs:
            verify_tar_dirs(
                ihier, tarball_dirs, ihier.add_unexpected_entries, controller
            )

        if unpacking_tarball_dirs:
            verify_tar_dirs(
                ihier, unpacking_tarball_dirs, ihier.add_unexpected_entries, controller,
            )

    return 0


# Results Hierarchy
def verify_user_arg(rhier, mdlogcfg, controller, path):
    """fetch user from the config file and verify its validity"""

    if rhier.path.parent == rhier.config.USERS:
        """We are reviewing a user tree, so check the user in
        the configuration.  Version 002 agents use the
        metadata log to store a user as well.
        """
        user_arg = rhier.path.name
        user = ""
        try:
            user = mdlogcfg.get("run", "user")
        except NoSectionError:
            pass
        except NoOptionError:
            pass
        if not user:
            """No user in the metadata.log of the tar ball, but
            we are examining a link in the user tree that
            does not have a configured user, report it.
            """
            rhier.add_unexpected_entries(
                Hierarchy.UNEXPECTED_USER_LINKS, controller, path
            )
        elif user_arg != user:
            """Configured user does not match the user tree in
            which we found the link."""
            rhier.add_unexpected_entries(Hierarchy.WRONG_USER_LINKS, controller, path)

    return 0


def path_below_controller(dir_path, controller):
    # FIXME: other possible ways to do this
    controller_path = os.path.join(controller, "")
    path = dir_path.split(controller_path, 1)[1]

    return Path(path)


def list_direct_entries(hierarchy, controller):

    direct_entries = list()
    for root, dirs, files in os.walk(Path(hierarchy, controller), topdown=True):
        for name in files:
            direct_entries.append(Path(root, name))
        for name in dirs:
            direct_entries.append(Path(root, name))

    return direct_entries


def verify_results(rhier, verifylist):
    """'rhier' is ResultsHierarchy class. """

    for controller in verifylist:
        if not Path(rhier.config.ARCHIVE, controller).is_dir():
            """Skip incoming controller directories that don't have an $ARCHIVE
            directory, handled in another part of the audit.
            """
            continue

        direct_entries = list_direct_entries(rhier.path, controller)
        rhier.add_controller(controller)

        for dir_path in direct_entries:
            path = path_below_controller(str(dir_path), controller)
            if dir_path.is_dir() and len(os.listdir(dir_path)) == 0:
                rhier.add_unexpected_entries(
                    Hierarchy.EMPTY_TARBALL_DIRS, controller, path
                )
            elif dir_path.is_symlink():
                link = os.path.realpath(str(dir_path))
                tb = f"{path.name}.tar.xz"
                incoming_path = Path(rhier.config.INCOMING, controller, dir_path.name)
                if not Path(rhier.config.ARCHIVE, controller, tb).exists():
                    rhier.add_unexpected_entries(
                        Hierarchy.INVALID_TB_LINKS, controller, dir_path.name
                    )
                else:
                    if link != str(incoming_path):
                        rhier.add_unexpected_entries(
                            Hierarchy.INCORRECT_TB_DIR_LINKS, controller, dir_path.name
                        )
                    elif not incoming_path.is_dir() and not incoming_path.is_symlink():
                        rhier.add_unexpected_entries(
                            Hierarchy.INVALID_TB_DIR_LINKS, controller, dir_path.name
                        )
                    else:
                        prefix_path = str(path.parent)
                        prefix_file = Path(
                            rhier.config.ARCHIVE,
                            controller,
                            ".prefix",
                            f"{dir_path.name}.prefix",
                        )
                        mdlogcfg = PbenchMDLogConfig(
                            Path(incoming_path, "metadata.log")
                        )
                        prefix = ""
                        try:
                            prefix = mdlogcfg.get("run", "prefix")
                        except NoSectionError:
                            pass
                        except NoOptionError:
                            pass
                        if prefix_path == ".":
                            if prefix:
                                rhier.add_unexpected_entries(
                                    Hierarchy.BAD_PREFIXES, controller, path
                                )
                            elif prefix_file.exists():
                                rhier.add_unexpected_entries(
                                    Hierarchy.UNUSED_PREFIX_FILES, controller, path
                                )
                        else:
                            if prefix:
                                if prefix != prefix_path:
                                    rhier.add_unexpected_entries(
                                        Hierarchy.BAD_PREFIXES, controller, path
                                    )
                            elif not prefix_file.exists():
                                rhier.add_unexpected_entries(
                                    Hierarchy.MISSING_PREFIX_FILES, controller, path
                                )
                            else:
                                f = 0
                                try:
                                    with prefix_file.open(mode="r") as file:
                                        prefix = file.read().replace("\n", "")
                                except Exception:
                                    f = 1
                                if f == 1:
                                    rhier.add_unexpected_entries(
                                        Hierarchy.BAD_PREFIX_FILES, controller, path
                                    )
                                else:
                                    if prefix != prefix_path:
                                        rhier.add_unexpected_entries(
                                            Hierarchy.BAD_PREFIXES, controller, path
                                        )
                        verify_user_arg(rhier, mdlogcfg, controller, path)
    return 0


# Controller Hierarchy
def verify_controllers(hier):
    """ 'hier' is a ControllerHierarchy class object. """
    controllers = Path(hier.path).glob("*")
    verify_valid_controllers(hier, controllers)

    for controller in hier.controllers:
        dir_path = Path(hier.path, controller)
        unexpected_dirs = list()
        if not Path(hier.config.ARCHIVE, controller).is_dir():
            """We have a controller in the hierarchy which does not have a
            controller of the same name in the archive hierarchy.  All
            we do is report it, don't bother analyzing it further.
            """
            hier.add_controller_list(Hierarchy.MIALIST, Path(controller).name)
        else:
            """Report any controllers with objects other than directories
            and links, while also recording any empty controllers.
            """
            count_dir_entries = 0
            direct_entries = dir_path.glob("*")
            for item_path in direct_entries:
                count_dir_entries += 1
                if not item_path.is_dir() and not item_path.is_symlink():
                    unexpected_dirs.append(controller)
                    break
            else:
                if count_dir_entries == 0:
                    hier.add_controller_list(Hierarchy.EMPTY_CONTROLLERS, controller)
                    continue

            if unexpected_dirs:
                hier.add_controller_list(Hierarchy.UNEXPECTED_CONTROLLERS, controller)
            hier.add_verify_list(controller)

    return 0


# User Hierarchy
def verify_users(hier):
    """ 'hier' is UserHierarchy class object."""
    if not Path(hier.path).is_dir():
        print(
            f"The setting for USERS in the config file is {hier.path}, but that is"
            f" not a directory"
        )
        return 1

    user_dirs = Path(hier.path).glob("*")

    for user_path in user_dirs:
        if user_path.is_dir():
            hier.add_user_dir(user_path)
        else:
            hier.add_unexpected_objects(user_path.name)

    return 0


def check_and_dump(f, hier, ihier):

    cnt = 0
    first_check = hier.check_controller()
    second_check = ihier.check_controller()
    if first_check or second_check:
        hier.header(f, "start")
        if first_check:
            cnt = hier.dump(f)
        if second_check:
            cnt += ihier.dump(f)
        hier.header(f, "end")
    return cnt


def check_directory_exists(pbdir_path, pbdirname):
    """ checks the existence of directories """
    pbdir = Path(pbdir_path)
    try:
        pbdir_p = pbdir.resolve(strict=True)
    except FileNotFoundError:
        print(f"{_NAME_}: Bad {pbdirname}={pbdir}", file=sys.stderr)
        return 1

    if not pbdir_p.is_dir():
        print(f"{_NAME_}: Bad {pbdirname}={pbdir}", file=sys.stderr)
        return 1

    return 0


def main():
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set CONFIG env variable",
            file=sys.stderr,
        )
        return 2

    try:
        config = PbenchServerConfig(cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e} (config file {cfg_name})", file=sys.stderr)
        return 1

    if check_directory_exists(config.ARCHIVE, "ARCHIVE") > 0:
        return 1

    if check_directory_exists(config.INCOMING, "INCOMING") > 0:
        return 1

    if check_directory_exists(config.RESULTS, "RESULTS") > 0:
        return 1

    if check_directory_exists(config.USERS, "USERS") > 0:
        return 1

    logger = get_pbench_logger(_NAME_, config)

    ret = 0

    try:
        Path(config.LOGSDIR, "pbench-audit-server").mkdir()
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        print("os.mkdir: Unable to create destination directory")
        return 1
    logfile = Path(config.LOGSDIR, "pbench-audit-server", "pbench-audit-server.log")
    # TEMPORARY addition of error file for the sake of test cases
    errorfile = Path(config.LOGSDIR, "pbench-audit-server", "pbench-audit-server.error")
    with errorfile.open(mode="w") as f:
        pass
    # END

    logger.info("start-{}", config.TS)

    with logfile.open(mode="w") as f:

        ahier = ArchiveHierarchy("archive", config.ARCHIVE, config)
        verify_archive(ahier)
        cnt = 0
        if ahier.check_controller():
            f.write(f"\nstart-{config.TS[4:]}: archive hierarchy: {config.ARCHIVE}\n")
            cnt = ahier.dump(f)
            ahier.header(f, "end")
        if cnt > 0:
            ret += 1

        ihier = IncomingHierarchy("Incoming", config.INCOMING, config)
        cihier = ControllerHierarchy("incoming", config.INCOMING, config)
        verify_controllers(cihier)
        verify_incoming(ihier, cihier.verifylist)
        cnt = check_and_dump(f, cihier, ihier)
        if cnt > 0:
            ret += 1

        rhier = ResultsHierarchy("Results", config.RESULTS, config)
        crhier = ControllerHierarchy("results", config.RESULTS, config)
        verify_controllers(crhier)
        verify_results(rhier, crhier.verifylist)
        cnt = check_and_dump(f, crhier, rhier)
        if cnt > 0:
            ret += 1

        uhier = UserHierarchy("users", config.USERS, config)
        verify_users(uhier)
        if uhier.users:
            for user in uhier.users:
                verify_results(user, crhier.verifylist)
        cnt = 0
        if uhier.check_controller():
            uhier.header(f, "start")
            cnt = uhier.dump(f)
            uhier.header(f, "end")
        if cnt > 0:
            ret += 1

    # prepare and send report
    with tempfile.NamedTemporaryFile(mode="w+t", dir=config.TMP) as reportfp:
        with open(logfile, "r") as f:
            reportfp.write(
                f"{_NAME_}.run-{config.timestamp()}({config.PBENCH_ENV})\n{f.read()}"
            )
            reportfp.seek(0)

            report = Report(config, _NAME_)
            report.init_report_template()
            try:
                report.post_status(config.timestamp(), "status", reportfp.name)
            except Exception:
                pass

    f.close()

    return ret


if __name__ == "__main__":
    sts = main()
    sys.exit(sts)
