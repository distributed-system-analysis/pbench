""" Collection and Structure Module for pbench-audit-server
"""

import os
import stat
import time

from collections import OrderedDict
from pathlib import Path
from typing import IO, List

from pbench.server import PbenchServerConfig


class Hierarchy:
    """Super class of Hierarchies"""

    UNEXPECTED_DIRS = "unexpected_dirs"
    SUBDIR_STATUS_INDICATORS = "subdir_status_indicators"
    UNEXPECTED_SYMLINKS = "unexpected_symlinks"
    UNEXPECTED_OBJECTS = "unexpected_objects"
    NON_PREFIXES = "non_prefixes"
    WRONG_PREFIXES = "wrong_prefixes"
    PREFIX_STATUS_INDICATORS = "prefix_status_indicators"
    MIALIST = "mialist"
    EMPTY_CONTROLLERS = "empty_controllers"
    UNEXPECTED_CONTROLLERS = "unexpected_controllers"
    INVALID_TB_DIRS = "invalid_tb_dirs"
    EMPTY_TARBALL_DIRS = "empty_tarball_dirs"
    INVALID_UNPACKING_DIRS = "invalid_unpacking_dirs"
    TARBALL_LINKS = "tarball_links"
    INVALID_TB_LINKS = "invalid_tb_links"
    INCORRECT_TB_DIR_LINKS = "incorrect_tb_dir_links"
    INVALID_TB_DIR_LINKS = "invalid_tb_dir_links"
    UNUSED_PREFIX_FILES = "unused_prefix_files"
    MISSING_PREFIX_FILES = "missing_prefix_files"
    BAD_PREFIX_FILES = "bad_prefix_files"
    BAD_PREFIXES = "bad_prefixes"
    UNEXPECTED_USER_LINKS = "unexpected_user_links"
    WRONG_USER_LINKS = "wrong_user_links"
    INCONCEIVABLE = "inconceivable"
    ERROR = "error"
    SUBDIR = "subdirs"
    PREFIX_DIR = "prefix_dir"

    def __init__(self, name: str, path: Path, config: PbenchServerConfig):
        self.name = name
        self.path = path
        self.config = config
        self.lead_tab = "\t\t"
        self.controllers = list()
        self.bad_controllers = list()
        self.validation_list = dict()

    def add_controller(self, controller: str):
        self.controllers.append(controller)

    def add_bad_controller(self, controller: str):
        self.bad_controllers.append(controller)

    def add_error_or_inconceivable_entries(self, val: str, controller: str, dirs: str):
        """Args:

            val -- Discrete Values for which the collection takes place
            controller -- the name of the controller associated with the
                        tar ball
            dirs -- directories associated with that controller
        """
        self.validation_list[val][controller] = dirs

    def add_unexpected_entries(self, val: str, controller: str, dirs: str):
        self.add_error_or_inconceivable_entries(val, controller, dirs)

    def header(self, fp: IO, status: str, is_newline: bool):
        """Adds main starting and ending message for each Hierarchy"""
        newline = "\n" if is_newline else ""
        fp.write(
            f"\n{status}-{self.config.TS[4:]}: {self.name} hierarchy: {self.path}{newline}\n"
        )

    def is_controller_in_list(self, controller: str) -> bool:
        """Returns whether the specified controller is in any of the validation lists"""
        for key in self.validation_list:
            if controller in self.validation_list[key]:
                return True
        return False

    def dump_check(
        self, fp: IO, controller: str, key: str, cnt: int, lead_tab: str, hierarchy: str
    ) -> int:
        """Output Messages for each list of controllers, files, directories, etc
        and depicting their cause of being added to that list or dictionary

        Args-

            fp -- file object for writing to the pbench-audit-server.log file
            controller -- name of the controller associated with the tar ball
            key -- Discrete Values for which the collection takes place
            cnt -- flag to check whether there is anything to report
            lead_tab -- tab space that needs to be associated with the result
                        message of each hierarchy result
            hierarchy -- name of the hierarchy
        """
        lead_asterisk = "\t* " if hierarchy == "archive" else "\t"
        if controller in self.validation_list[key]:
            fp.write(f"{lead_asterisk}{self.validation_list[key].get_msg()}\n")
            if key in [
                self.SUBDIR_STATUS_INDICATORS,
                self.PREFIX_STATUS_INDICATORS,
            ] or self.output_format(
                fp, self.validation_list[key][controller], cnt, lead_tab, hierarchy
            ):
                cnt = 1
        return cnt

    def output_format(
        self, fp: IO, ctrl_tb_list: List, cnt: int, lead_tab: str, hierarchy: str,
    ) -> int:
        """
        Args:

            ctrl_tb_list -- list of controllers and tarballs that are
                                associated with the discrete values

        """
        if hierarchy == "archive":
            fp.write("\t  ++++++++++\n")
        for value in sorted(ctrl_tb_list):
            fp.write(f"{lead_tab}{value}\n")
        if hierarchy == "archive":
            fp.write("\t  ----------\n")
        cnt = 1
        return cnt


class DictOfList(OrderedDict):
    """Class to add controller and tarballs as dictionary for
    discrete fields
    {
        fixed_val1:
            DictOfList([(ctrl1, [tb1, tb2])]),
        fixed_val2:
            DictOfList([(ctrl2: [tb3])])
    }
    """

    def __init__(self, msg: str):
        super().__init__()
        self._msg = msg

    def get_msg(self):
        return self._msg

    def __setitem__(self, key: str, value: str):
        if key in self:
            self[key].append(value)
        else:
            super().__setitem__(key, [value])


class ListOfController(list):
    """Class used to add list of elements to Dictionary
    {
        val1: [controller1],
        val2: [controller2],
        val3: [controller3, controller4]
    }
    """

    def __init__(self, msg: str):
        super().__init__()
        self._msg = msg

    def get_msg(self):
        return self._msg


class ArchiveHierarchy(Hierarchy):
    def __init__(self, name: str, path: Path, config: PbenchServerConfig):
        super().__init__(name, path, config)

        self.tarballs = list()
        self.lead_tab = "\t  "
        self.validation_list = {
            self.UNEXPECTED_DIRS: DictOfList(
                "Unexpected state directories found in this controller directory:"
            ),
            self.SUBDIR_STATUS_INDICATORS: DictOfList(
                "No state directories found in this controller directory."
            ),
            self.UNEXPECTED_SYMLINKS: DictOfList(
                "Unexpected symlinks in controller directory:"
            ),
            self.UNEXPECTED_OBJECTS: DictOfList(
                "Unexpected files in controller directory:"
            ),
            self.NON_PREFIXES: DictOfList(
                "Unexpected file system objects in .prefix directory:"
            ),
            self.WRONG_PREFIXES: DictOfList(
                "Wrong prefix file names found in /.prefix directory:"
            ),
            self.PREFIX_STATUS_INDICATORS: DictOfList(
                "Prefix directory, .prefix, is not a directory!"
            ),
            self.ERROR: DictOfList("ERROR:"),
            self.INCONCEIVABLE: DictOfList("Inconceivable Conditions:"),
        }

    def add_tarballs(self, controller: str):
        """Add controllers which consist of tarballs"""
        self.tarballs.append(controller)

    def dump(self, fp: IO) -> int:
        """Checks and Output collected data"""
        cnt = 0
        if self.bad_controllers:
            self.output_bad_controllers(fp)
            cnt = 1
        for controller in sorted(self.controllers):
            check = self.is_controller_in_list(controller)
            if check or controller not in self.tarballs:
                fp.write(f"\nController: {controller}\n")
                for key in self.validation_list:
                    cnt = self.dump_check(
                        fp, controller, key, cnt, self.lead_tab, self.name
                    )
                if controller not in self.tarballs:
                    fp.write(
                        f"{self.lead_tab[:-2]}* No tar ball files found in this controller directory.\n"
                    )
                    cnt = 1
        return cnt

    def check_controller(self) -> bool:
        for controller in self.controllers:
            if (
                self.is_controller_in_list(controller)
                or controller not in self.tarballs
            ):
                return True
        return False

    def output_bad_controllers(self, fp: IO):
        fp.write("\nBad Controllers:\n")
        for controller in sorted(self.bad_controllers):
            """Formatting output into ls -l format"""
            contStatOb = os.stat(controller)
            fperm = stat.filemode(contStatOb.st_mode)
            mTime = time.strftime(
                "%a %b %d %H:%M:%S.0000000000 %Y", time.gmtime(contStatOb.st_mtime)
            )
            fp.write(f"\t{fperm}          0 {mTime} {controller.name}\n")


class ControllerHierarchy(Hierarchy):
    def __init__(self, name: str, path: Path, config: PbenchServerConfig):
        super().__init__(name, path, config)

        self.verifylist = set()
        self.lead_tab = "\t"
        self.validation_list = {
            self.MIALIST: ListOfController(
                f"Controllers which do not have a {self.config.ARCHIVE} directory:"
            ),
            self.EMPTY_CONTROLLERS: ListOfController("Controllers which are empty:"),
            self.UNEXPECTED_CONTROLLERS: ListOfController(
                "Controllers which have unexpected objects:"
            ),
        }

    def add_controller_list(self, val: str, controller: str):
        """Gather controllers for each discrete values"""
        self.validation_list[val].append(controller)

    def add_verify_list(self, controller: str):
        if controller not in self.verifylist:
            self.verifylist.add(controller)

    def check_controller(self) -> List:
        return self.bad_controllers or any(
            [self.validation_list[val] for val in self.validation_list]
        )

    def dump(self, fp: IO) -> int:
        cnt = 0
        if self.bad_controllers:
            fp.write("\nUnexpected files found:\n")
            for controller in sorted(self.bad_controllers):
                fp.write(f"\t{controller.name}\n")
            cnt = 1
        for val in self.validation_list:
            if self.validation_list[val]:
                fp.write(f"\n{self.validation_list[val].get_msg()}\n")
                cnt = self.output_format(
                    fp, self.validation_list[val], cnt, self.lead_tab, self.name
                )
        return cnt


class IRHierarchy:
    """Deals with both Incoming and Results Hierarchy
        * checks whether the controllers are present in the controllers list
        * Validates and Output the collected Data
    """

    def check_controller(self) -> bool:
        for controller in self.controllers:
            if self.is_controller_in_list(controller):
                return True
        return False

    def dump(self, fp: IO) -> int:
        cnt = 0
        for controller in sorted(self.controllers):
            if self.is_controller_in_list(controller):
                fp.write(f"\n{self.name} issues for controller: {controller}\n")
                for key in self.validation_list:
                    cnt = self.dump_check(
                        fp, controller, key, cnt, self.lead_tab, self.name
                    )

        return cnt


class IncomingHierarchy(Hierarchy, IRHierarchy):
    def __init__(self, name: str, path: Path, config: PbenchServerConfig):
        super().__init__(name, path, config)

        self.validation_list = {
            self.INVALID_TB_DIRS: DictOfList(
                f"Invalid tar ball directories (not in {self.config.ARCHIVE}):"
            ),
            self.EMPTY_TARBALL_DIRS: DictOfList("Empty tar ball directories:"),
            self.INVALID_UNPACKING_DIRS: DictOfList(
                "Invalid unpacking directories (missing tar ball):"
            ),
            self.TARBALL_LINKS: DictOfList("Invalid tar ball links:"),
            self.INCONCEIVABLE: DictOfList("Inconceivable Conditions:"),
        }


class ResultsHierarchy(Hierarchy, IRHierarchy):
    def __init__(
        self, name: str, path: Path, config: PbenchServerConfig, global_results=False
    ):
        super().__init__(name, path, config)

        self.global_results = global_results
        self.validation_list = {
            self.EMPTY_TARBALL_DIRS: DictOfList("Empty tar ball directories:"),
            self.INVALID_TB_LINKS: DictOfList(
                f"Invalid tar ball links (not in {self.config.ARCHIVE}):"
            ),
            self.INCORRECT_TB_DIR_LINKS: DictOfList(
                "Incorrectly constructed tar ball links:"
            ),
            self.INVALID_TB_DIR_LINKS: DictOfList(
                "Tar ball links to invalid incoming location:"
            ),
            self.UNUSED_PREFIX_FILES: DictOfList(
                "Tar ball links with unused prefix files:"
            ),
            self.MISSING_PREFIX_FILES: DictOfList(
                "Tar ball links with missing prefix files:"
            ),
            self.BAD_PREFIX_FILES: DictOfList("Tar ball links with bad prefix files:"),
            self.BAD_PREFIXES: DictOfList("Tar ball links with bad prefixes:"),
            self.UNEXPECTED_USER_LINKS: DictOfList(
                "Tar ball links not configured for this user:"
            ),
            self.WRONG_USER_LINKS: DictOfList("Tar ball links for the wrong user:"),
        }

    def dump(self, fp: IO) -> int:
        cnt = 0
        for controller in sorted(self.controllers):
            if self.is_controller_in_list(controller):
                if self.global_results:
                    fp.write(
                        f"\nResults issues for controller: {self.name}/{controller}\n"
                    )
                else:
                    fp.write(f"\n{self.name} issues for controller: {controller}\n")
                for key in self.validation_list:
                    cnt = self.dump_check(
                        fp, controller, key, cnt, self.lead_tab, self.name
                    )

        return cnt


class UserHierarchy(Hierarchy):
    def __init__(self, name: str, path: Path, config: PbenchServerConfig):
        super().__init__(name, path, config)

        self.users = list()
        self.unexpected_objects = list()
        # To check availability of controllers in another hierarchy
        self.check = False

    def add_unexpected_objects(self, user: str):
        self.unexpected_objects.append(user)

    def add_user_dir(self, user: str):
        self.users.append(
            ResultsHierarchy(
                user.name,
                Path(self.config.USERS, user),
                self.config,
                global_results=True,
            )
        )

    def check_controller(self):
        for user in self.users:
            if user.check_controller():
                self.check = True
                break
        return self.unexpected_objects or self.check

    def dump(self, fp: IO) -> int:
        cnt = 0
        if self.unexpected_objects:
            fp.write("\nUnexpected files found:\n")
            for controller in sorted(self.unexpected_objects):
                fp.write(f"\t{controller}\n")
            cnt = 1

        if self.check:
            for user in self.users:
                cnt = user.dump(fp)

        return cnt
