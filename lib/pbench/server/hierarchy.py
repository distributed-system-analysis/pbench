""" Collection and Structure Module for pbench-audit-server
"""

import os
import time

from pathlib import Path
from collections import OrderedDict


permdict = {
    "0": "---",
    "1": "--x",
    "2": "-w-",
    "3": "-wx",
    "4": "r--",
    "5": "r-x",
    "6": "rw-",
    "7": "rwx",
}


def filepermissions(mode):
    """Convert File permissions from numeric to symbolic.
    from '755' --> 'rwxr-xr-x' """
    fperm = ""
    modebits = oct(mode)[-3:]
    for bits in modebits:
        try:
            fperm += permdict[bits]
        except IndexError:
            raise ValueError(
                f"Could not find key '{bits}' in file permissions dictionary"
            )

    return fperm


class Hierarchy(object):
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

    def __init__(self, name, path, config):
        self.name = name
        self.path = path
        self.config = config
        self.controllers = list()
        self.bad_controllers = list()
        self.validation_list = None

    def add_controller(self, controller):
        self.controllers.append(controller)

    def add_bad_controller(self, controller):
        self.bad_controllers.append(controller)

    def add_error_or_inconceivable_entries(self, val, controller, dirs):
        self.validation_list[val][controller] = dirs

    def add_unexpected_entries(self, val, controller, dirs):
        """Gather values for each validation_list dict key"""
        self.validation_list[val][controller] = dirs

    def header(self, fp, status):
        """Adds main starting and ending messages for each Hierarchy"""
        lead_newline = "\n" if status == "start" else ""
        fp.write(
            f"{lead_newline}\n{status}-{self.config.TS[4:]}: {self.name} hierarchy: {self.path}\n"
        )
        return

    def check_controller_in_list(self, controller):
        """Checks whether there are controllers in dictionary or not"""
        return any(
            [
                controller in self.validation_list[key]._dict
                for key in self.validation_list
            ]
        )

    """
    ##FIXME: The mention of hierarchies(archive, controller) from here on, in
            Hierarchy class is mainly to keep the format algned with the shell script
    """

    def dump_check(self, fp, controller, key, cnt, hierarchy=False):
        """Output Messages for each list of controllers, files,
        directories, etc depicting their cause of being added to
        that list or dictionary
        """
        lead_asterisk = "\t* " if hierarchy == "archive" else "\t"
        if controller in self.validation_list[key]._dict:
            if key not in ["subdir_status_indicators", "prefix_status_indicators"]:
                fp.write(f"{lead_asterisk}{self.validation_list[key]._get_msg()}\n")
                if hierarchy == "archive":
                    cnt = self.output_format(
                        fp, self.validation_list[key]._dict[controller], cnt, "archive"
                    )
                else:
                    cnt = self.output_format(
                        fp, self.validation_list[key]._dict[controller], cnt
                    )
            elif "subdirs" in self.validation_list[key]._dict[controller]:
                fp.write(f"{lead_asterisk}{self.validation_list[key]._get_msg()}\n")
                cnt += 1
            elif "prefix_dir" in self.validation_list[key]._dict[controller]:
                fp.write(f"{lead_asterisk}{self.validation_list[key]._get_msg()}\n")
                cnt += 1
        return cnt

    def check_tab_format(self, hierarchy):
        """Check the format of tab acc. to hierarchy"""

        lead_tab = ""
        if hierarchy == "controller":
            lead_tab = "\t"
        elif hierarchy == "archive":
            lead_tab = "\t  "

        return lead_tab

    def output_format(self, fp, controller_list, cnt, hierarchy=False):
        """Output format of list"""

        lead_tab = self.check_tab_format(hierarchy) if hierarchy else "\t\t"
        if hierarchy == "archive":
            fp.write("\t  ++++++++++\n")
        self.output_list(fp, lead_tab, controller_list)
        if hierarchy == "archive":
            fp.write("\t  ----------\n")
        cnt += 1
        return cnt

    def output_list(self, fp, lead_tab, controller_list):
        """ Writing list value to file"""
        for value in sorted(controller_list):
            fp.write(f"{lead_tab}{value}\n")
        return


class DictOfList(object):
    """Class used to create and add elements to Dictionary"""

    def __init__(self, msg):
        self._dict = OrderedDict()
        self._msg = msg

    def _get_msg(self):
        return self._msg

    def __setitem__(self, key, value):
        if key in self._dict:
            self._dict[key].append(value)
        else:
            self._dict[key] = [value]


class List(object):
    """Class used to create and add elements to Dictionary"""

    def __init__(self, msg):
        self._list = list()
        self._msg = msg

    def _get_msg(self):
        return self._msg

    def additem(self, value):
        self._list.append(value)

    def getlist(self):
        return self._list


class ArchiveHierarchy(Hierarchy):
    def __init__(self, name, path, config):
        super().__init__(name, path, config)

        self.tarballs = list()
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

    def add_tarballs(self, controller):
        self.tarballs.append(controller)

    def dump(self, fp):
        """Checks and Output collected data"""
        cnt = 0
        if self.bad_controllers:
            self.output_bad_controllers(fp)
            cnt += 1
        for controller in sorted(self.controllers):
            check = self.check_controller_in_list(controller)
            if check or controller not in self.tarballs:
                fp.write(f"\nController: {controller}\n")
                for key in self.validation_list:
                    cnt += self.dump_check(fp, controller, key, cnt, "archive")
                if controller not in self.tarballs:
                    fp.write(
                        "\t* No tar ball files found in this controller directory.\n"
                    )
                    cnt += 1
        return cnt

    def check_controller(self):
        for controller in sorted(self.controllers):
            if (
                self.check_controller_in_list(controller)
                or controller not in self.tarballs
            ):
                return True
        return False

    def output_bad_controllers(self, fp):
        fp.write("\nBad Controllers:\n")
        for controller in sorted(self.bad_controllers):
            """Formatting output into ls -l format to align
            output with gold files
            """
            contStatOb = os.stat(controller)
            fperm = filepermissions(contStatOb.st_mode)
            mTime = time.strftime(
                "%a %b %d %H:%M:%S.0000000000 %Y", time.gmtime(contStatOb.st_mtime)
            )
            fp.write(f"\t-{fperm}          0 {mTime} {controller.name}\n")
        return


class ControllerHierarchy(Hierarchy):
    def __init__(self, name, path, config):
        super().__init__(name, path, config)

        self.verifylist = list()
        self.validation_list = {
            self.MIALIST: List(
                f"Controllers which do not have a {self.config.ARCHIVE} directory:"
            ),
            self.EMPTY_CONTROLLERS: List("Controllers which are empty:"),
            self.UNEXPECTED_CONTROLLERS: List(
                "Controllers which have unexpected objects:"
            ),
        }

    def add_controller_list(self, val, controller):
        """Gather values for each controller_check dict key"""
        self.validation_list[val].additem(controller)

    def add_verify_list(self, controller):
        if controller not in self.verifylist:
            self.verifylist.append(controller)

    def check_controller(self):
        return self.bad_controllers or any(
            [self.validation_list[val].getlist() for val in self.validation_list]
        )

    def dump(self, fp):
        """Validates and Output collected Hierarchy data"""
        cnt = 0
        if self.bad_controllers:
            fp.write("\nUnexpected files found:\n")
            for controller in sorted(self.bad_controllers):
                fp.write(f"\t{controller.name}\n")
            cnt = cnt + 1
        for val in self.validation_list:
            if self.validation_list[val].getlist():
                fp.write(f"\n{self.validation_list[val]._get_msg()}\n")
                cnt += self.output_format(
                    fp, self.validation_list[val].getlist(), cnt, "controller"
                )
        return cnt


class IRHierarchy(object):
    def check_controller(self):
        for controller in sorted(self.controllers):
            if self.check_controller_in_list(controller):
                return True
        return False

    def dump(self, fp):
        """Validates and Output collected data"""
        cnt = 0
        for controller in sorted(self.controllers):
            if self.check_controller_in_list(controller):
                fp.write(f"\n{self.name} issues for controller: {controller}\n")
                for key in self.validation_list:
                    cnt = self.dump_check(fp, controller, key, cnt)

        return cnt


class IncomingHierarchy(Hierarchy, IRHierarchy):
    def __init__(self, name, path, config):
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
    def __init__(self, name, path, config, global_results=False):
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

    def dump(self, fp):
        """Validates and Output collected data"""
        cnt = 0
        for controller in sorted(self.controllers):
            if self.check_controller_in_list(controller):
                if self.global_results:
                    fp.write(
                        f"\nResults issues for controller: {self.name}/{controller}\n"
                    )
                else:
                    fp.write(f"\n{self.name} issues for controller: {controller}\n")
                for key in self.validation_list:
                    cnt = self.dump_check(fp, controller, key, cnt)

        return cnt


class UserHierarchy(Hierarchy):
    def __init__(self, name, path, config):
        super().__init__(name, path, config)

        self.users = list()
        self.unexpected_objects = list()
        # To check availability of controllers in another hierarchy
        self.check = False

    def add_unexpected_objects(self, user):
        self.unexpected_objects.append(user)

    def add_user_dir(self, user):
        self.users.append(
            ResultsHierarchy(
                user.name, Path(self.config.USERS, user), self.config, True
            )
        )

    def check_controller(self):
        for user in self.users:
            if user.check_controller():
                self.check = True
                break
        return self.unexpected_objects or self.check

    def dump(self, fp):
        """Validates and Output Collected data"""
        cnt = 0
        if self.unexpected_objects:
            fp.write("\nUnexpected files found:\n")
            for controller in sorted(self.unexpected_objects):
                fp.write(f"\t{controller}\n")
            cnt = cnt + 1

        if self.check:
            for user in self.users:
                cnt += user.dump(fp)

        return cnt
