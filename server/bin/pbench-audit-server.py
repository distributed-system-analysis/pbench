#! /usr/bin/env python3

import os
import sys
import glob
import time
import tempfile

from pathlib import Path
from pbench import PbenchConfig
from pbench.common.exceptions import BadConfig
from pbench.server.logger import get_pbench_logger
from pbench.server.report import Report
from configparser import ConfigParser, NoSectionError, NoOptionError


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


class DictOfList(object):
    """Class used to create and add elements to Dictionary
    """

    def __init__(self):
        self._dict = {}

    def add_entry(self, key, value):
        if key in self._dict:
            self._dict.get(key).append(value)
        else:
            self._dict[key] = [value]


class Hierarchy(object):
    def __init__(self, name, path, config):
        self.name = name
        self.path = path
        self.config = config


def filepermission(fileperm):
    stat = ""
    while fileperm > 0:
        mod = fileperm % 10
        permdict = {
            0: "---",
            1: "--x",
            2: "-w-",
            3: "-wx",
            4: "r--",
            5: "r-x",
            6: "rw-",
            7: "rwx",
        }
        res = permdict[mod]
        stat = res + stat
        fileperm = fileperm // 10

    return f"-{stat}"


def header(f, stat, timestamp, hierarchy, path):
    if stat == "start":
        f.write(f"\n\n{stat}-{timestamp}: {hierarchy} hierarchy: {path}\n")
    else:
        f.write(f"\n{stat}-{timestamp}: {hierarchy} hierarchy: {path}\n")


class ArchiveHierarchy(Hierarchy):
    def __init__(self, name, path, config):
        super().__init__(name, path, config)

        self.controllers = list()
        self.bad_controllers = list()
        self.tarballs = list()
        self.things_to_check = {
            "unexpected_symlinks": DictOfList(),
            "unexpected_objects": DictOfList(),
            "expected_objects": DictOfList(),
            "unexpected_dirs": DictOfList(),
            "non_prefixes": DictOfList(),
            "wrong_prefixes": DictOfList(),
            "non_prefix_dirs": DictOfList(),
            "status_indicators": DictOfList(),
        }

    def add_controller(self, controller):
        self.controllers.append(controller)

    def add_bad_controller(self, controller):
        self.bad_controllers.append(controller)

    def add_tarballs(self, controller):
        self.tarballs.append(controller)

    def add_unexpected_symlinks(self, controller, link):
        self.things_to_check["unexpected_symlinks"].add_entry(controller, link)

    def add_unexpected_objects(self, controller, obj):
        self.things_to_check["unexpected_objects"].add_entry(controller, obj)

    def add_unexpected_dirs(self, controller, dirs):
        self.things_to_check["unexpected_dirs"].add_entry(controller, dirs)

    def add_non_prefixes(self, controller, prefix):
        self.things_to_check["non_prefixes"].add_entry(controller, prefix)

    def add_wrong_prefixes(self, controller, prefix):
        self.things_to_check["wrong_prefixes"].add_entry(controller, prefix)

    def set_status(self, controller, subdir):
        self.things_to_check["status_indicators"].add_entry(controller, subdir)

    def dump(self, f):
        cnt = 0
        check_h = False
        for controller in sorted(self.controllers):
            check_h = any(
                [
                    controller in self.things_to_check[k]._dict
                    or controller not in self.tarballs
                    for k in self.things_to_check
                ]
            )
        if check_h or self.bad_controllers:
            f.write(f"\nstart-{self.config.TS[4:]}: archive hierarchy: {self.path}\n")
            if self.bad_controllers:
                f.write("\nBad Controllers:\n")
                cnt += 1
                for controller in sorted(self.bad_controllers):
                    contStatOb = os.stat(controller)
                    fperm = filepermission(int(oct(contStatOb.st_mode)[-3:]))
                    mTime = time.strftime(
                        "%a %b %d %H:%M:%S.0000000000 %Y",
                        time.gmtime(contStatOb.st_mtime),
                    )
                    bname = os.path.basename(controller)
                    f.write(f"\t{fperm}          0 {mTime} {bname}\n")
            for controller in sorted(self.controllers):
                check = any(
                    [
                        controller in self.things_to_check[k]._dict
                        for k in self.things_to_check
                    ]
                )
                if check or controller not in self.tarballs:
                    f.write(f"\nController: {controller}\n")
                    if controller in self.things_to_check["unexpected_dirs"]._dict:
                        f.write(
                            "\t* Unexpected state directories found in this controller directory:\n"
                        )
                        cnt = self.output_format(f, controller, "unexpected_dirs", cnt)
                    if controller in self.things_to_check["status_indicators"]._dict:
                        if (
                            "subdirs"
                            in self.things_to_check["status_indicators"]._dict[
                                controller
                            ]
                        ):
                            f.write(
                                "\t* No state directories found in this controller directory.\n"
                            )
                        cnt += 1
                    if controller in self.things_to_check["unexpected_symlinks"]._dict:
                        f.write("\t* Unexpected symlinks in controller directory:\n")
                        cnt = self.output_format(
                            f, controller, "unexpected_symlinks", cnt
                        )
                    if controller in self.things_to_check["unexpected_objects"]._dict:
                        f.write("\t* Unexpected files in controller directory:\n")
                        cnt = self.output_format(
                            f, controller, "unexpected_objects", cnt
                        )
                    if controller not in self.tarballs:
                        f.write(
                            "\t* No tar ball files found in this controller directory.\n"
                        )
                        cnt += 1
                    if controller in self.things_to_check["non_prefixes"]._dict:
                        f.write(
                            "\t* Unexpected file system objects in .prefix directory:\n"
                        )
                        cnt = self.output_format(f, controller, "non_prefixes", cnt)
                    if controller in self.things_to_check["wrong_prefixes"]._dict:
                        f.write(
                            "\t* Wrong prefix file names found in /.prefix directory:\n"
                        )
                        cnt = self.output_format(f, controller, "wrong_prefixes", cnt)
                    if controller in self.things_to_check["status_indicators"]._dict:
                        if (
                            "prefix_dir"
                            in self.things_to_check["status_indicators"]._dict[
                                controller
                            ]
                        ):
                            f.write(
                                "\t* Prefix directory, .prefix, is not a directory!\n"
                            )
            f.write(f"\nend-{self.config.TS[4:]}: archive hierarchy: {self.path}\n")
        return cnt

    def output_format(self, f, controller, controller_val, cnt):
        f.write("\t  ++++++++++\n")
        for val in sorted(self.things_to_check[controller_val]._dict[controller]):
            f.write(f"\t  {val}\n")
        f.write("\t  ----------\n")
        cnt += 1
        return cnt


def verify_subdirs(hier, controller, states):
    linkdirs = sorted(hier.config.LINKDIRS.split(" "))
    if states:
        for state in states:
            if all(
                [
                    os.path.exists(os.path.join(hier.path, controller, state)),
                    state != "_QUARANTINED",
                    not state.startswith("WONT-INDEX"),
                ]
            ):
                if state not in linkdirs:
                    hier.add_unexpected_dirs(controller, state)
    else:
        hier.set_status(controller, "subdirs")

    return 0


def verify_prefixes(hier, controller):
    prefix_dir = os.path.join(hier.path, controller, ".prefix")
    if not os.path.exists(prefix_dir):
        return
    if not os.path.isdir(prefix_dir):
        hier.set_status(controller, "prefix_dir")
        return

    prefixes = glob.iglob(os.path.join(prefix_dir, "*"))

    for prefix in prefixes:
        base_prefix = os.path.basename(prefix)
        if not base_prefix.startswith("prefix.") and not base_prefix.endswith(
            ".prefix"
        ):
            hier.add_non_prefixes(controller, base_prefix)
        elif base_prefix.startswith("prefix."):
            hier.add_wrong_prefixes(controller, base_prefix)

    return


def verify_archive(hier):
    controllers = glob.iglob(os.path.join(hier.path, "*"))

    for controller in controllers:
        if os.path.isdir(controller):
            hier.add_controller(os.path.basename(controller))
        else:
            hier.add_bad_controller(controller)

    # now check each "good" controller and get the tarballs it contains
    for controller in hier.controllers:
        direct_entries = glob.iglob(os.path.join(hier.path, controller, "*"))
        hidden_entries = glob.glob(os.path.join(hier.path, controller, ".*"))
        if hidden_entries:
            for hid_entries in hidden_entries:
                if os.path.isfile(hid_entries):
                    hier.add_unexpected_objects(
                        controller, os.path.basename(hid_entries)
                    )
        controller_subdir = list()
        for item in direct_entries:
            base_item = os.path.basename(item)
            if os.path.isdir(item):
                controller_subdir.append(base_item)
            elif os.path.islink(item):
                symlink_item = f"{base_item} -> {os.path.realpath(item)}"
                hier.add_unexpected_symlinks(controller, symlink_item)
            elif all(
                [
                    os.path.isfile(item),
                    not base_item.endswith(".tar.xz"),
                    not base_item.endswith(".tar.xz.md5"),
                ]
            ):
                hier.add_unexpected_objects(controller, base_item)
            elif os.path.isfile(item) and (
                base_item.endswith(".tar.xz") or base_item.endswith(".tar.xz.md5")
            ):
                hier.add_tarballs(controller)
            else:
                print(
                    f"{base_item} item should have been handled by the above mentioned conditions. "
                    f"It is an unexpected item which should not have occured, "
                    f"leading to an inappropriate condition"
                )
        verify_subdirs(hier, controller, controller_subdir)
        verify_prefixes(hier, controller)

    return


class ControllerHierarchy(Hierarchy):
    def __init__(self, name, path, config):
        super().__init__(name, path, config)

        self.controllers = list()
        self.controller_check = {
            "unexpected_objects": list(),
            "mialist": list(),
            "unexpected_cls": list(),
            "empty_cls": list(),
        }
        self.verifylist = list()

    def add_controller(self, controller):
        self.controllers.append(controller)

    def add_unexpected_objects(self, controller):
        self.controller_check["unexpected_objects"].append(controller)

    def add_mialist(self, controller):
        self.controller_check["mialist"].append(controller)

    def add_empty_cls(self, controller):
        self.controller_check["empty_cls"].append(controller)

    def add_unexpected_cls(self, controller):
        self.controller_check["unexpected_cls"].append(controller)

    def add_verifylist(self, controller):
        if controller not in self.verifylist:
            self.verifylist.append(controller)

    def dump(self, f, ihier, chier):
        cnt = 0
        check = any([self.controller_check[val] for val in self.controller_check])
        if check:
            header(f, "start", self.config.TS[4:], self.name, self.path)
            if self.controller_check["unexpected_objects"]:
                f.write("\nUnexpected files found:\n")
                cnt = self.output_format(
                    f, self.controller_check["unexpected_objects"], cnt
                )
            if self.controller_check["mialist"]:
                f.write(
                    f"\nControllers which do not have a {self.config.ARCHIVE} directory:\n"
                )
                cnt = self.output_format(f, self.controller_check["mialist"], cnt)
            if self.controller_check["empty_cls"]:
                f.write("\nControllers which are empty:\n")
                cnt = self.output_format(f, self.controller_check["empty_cls"], cnt)
            if self.controller_check["unexpected_cls"]:
                f.write("\nControllers which have unexpected objects:\n")
                cnt = self.output_format(
                    f, self.controller_check["unexpected_cls"], cnt
                )
            if self.verifylist:
                cnt += ihier.dump(f, 0)
            header(f, "end", self.config.TS[4:], self.name, self.path)
        else:
            if self.verifylist:
                cnt += ihier.dump(f, 1, chier)
        return cnt

    def output_format(self, f, verify_tardir, cnt):
        for controller in sorted(verify_tardir):
            f.write(f"\t{controller}\n")
            cnt += 1
        return cnt


def verify_hierarchy(ihier, hier, hierarchy):

    hierchy = os.path.basename(hierarchy)
    users = hier.config.USERS

    if hier.verifylist:
        if hierchy == "incoming":
            verify_incoming(ihier, hier.verifylist)
        elif hierchy == "results":
            verify_results(ihier, hier)
        elif os.path.dirname(hierarchy) == users:
            verify_results(ihier, hier, hierchy)
        else:
            print(
                '${PROG}: verify_controllers bad argument, hierarchy_root="${hierarchy_root}"\n'
            )
            return 1
    return 0


def verify_controllers(ihier, hier, hierarchy):

    controllers = glob.iglob(os.path.join(hier.path, "*"))

    for controller in controllers:
        if os.path.isdir(controller):
            hier.add_controller(os.path.basename(controller))
        else:
            hier.add_unexpected_objects(os.path.basename(controller))

    if hier.controllers:
        for controller in hier.controllers:
            dirent = os.path.join(hier.path, controller)
            unexpected_dirs = list()
            if not os.path.isdir(os.path.join(hier.config.ARCHIVE, controller)):
                hier.add_mialist(os.path.basename(controller))
            else:
                if len(os.listdir(dirent)) == 0:
                    hier.add_empty_cls(controller)
                    continue
                else:
                    direct_entries = glob.iglob(
                        os.path.join(hier.path, controller, "*")
                    )
                    for item in direct_entries:
                        if not os.path.isdir(item) and not os.path.islink(item):
                            unexpected_dirs.append(controller)

                if unexpected_dirs:
                    hier.add_unexpected_cls(controller)
                hier.add_verifylist(controller)

    if verify_hierarchy(ihier, hier, hierarchy) > 0:
        return 1

    return 0


class IncomingHierarchy(object):
    def __init__(self, config):

        self.config = config
        self.controllers = list()
        self.incoming_check = {
            "invalid_tb_dirs": DictOfList(),
            "empty_tarball_dirs": DictOfList(),
            "invalid_unpacking_dirs": DictOfList(),
            "tarball_links": DictOfList(),
        }

    def add_controller(self, controller):
        self.controllers.append(controller)

    def add_invalid_tb_dirs(self, controller, dirt):
        self.incoming_check["invalid_tb_dirs"].add_entry(controller, dirt)

    def add_empty_tarball_dirs(self, controller, dirt):
        self.incoming_check["empty_tarball_dirs"].add_entry(controller, dirt)

    def add_invalid_unpacking_dirs(self, controller, dirt):
        self.incoming_check["invalid_unpacking_dirs"].add_entry(controller, dirt)

    def add_tarball_links(self, controller, dirt):
        self.incoming_check["tarball_links"].add_entry(controller, dirt)

    def dump(self, f, stat, hier=False):
        cnt = 0
        for verify_tardir in sorted(self.controllers):
            check = any(
                [
                    verify_tardir in self.incoming_check[k]._dict
                    for k in self.incoming_check
                ]
            )
            if check:
                cnt = 1
                if stat == 1:
                    header(f, "start", self.config.TS[4:], hier.name, hier.path)
                f.write(f"\nIncoming issues for controller: {verify_tardir}\n")
                if verify_tardir in self.incoming_check["invalid_tb_dirs"]._dict:
                    f.write(
                        f"\tInvalid tar ball directories (not in {self.config.ARCHIVE}):\n"
                    )
                    self.output_format(f, verify_tardir, "invalid_tb_dirs")
                if verify_tardir in self.incoming_check["empty_tarball_dirs"]._dict:
                    f.write("\tEmpty tar ball directories:\n")
                    self.output_format(f, verify_tardir, "empty_tarball_dirs")
                if verify_tardir in self.incoming_check["invalid_unpacking_dirs"]._dict:
                    f.write("\tInvalid unpacking directories (missing tar ball):\n")
                    self.output_format(f, verify_tardir, "invalid_unpacking_dirs")
                if verify_tardir in self.incoming_check["tarball_links"]._dict:
                    f.write("\tInvalid tar ball links:\n")
                    self.output_format(f, verify_tardir, "tarball_links")
                if stat == 1:
                    header(f, "end", self.config.TS[4:], hier.name, hier.path)

        return cnt

    def output_format(self, f, verify_tardir, dir_val):
        for val in sorted(self.incoming_check[dir_val]._dict[verify_tardir]):
            f.write(f"\t\t{val}\n")
        return 0


def verify_tar_dirs(ihier, tarball_dirs, tblist, controller):
    for tb in tarball_dirs:
        if tb.endswith("unpack"):
            tar = tb[:-7]
            tar = f"{tar}.tar.xz"
        else:
            tar = f"{tb}.tar.xz"
        tarfile = os.path.join(ihier.config.ARCHIVE, controller, tar)
        if os.path.exists(tarfile):
            with open(tarfile, "r") as f:
                try:
                    file_content = f.read(1)
                    if file_content:
                        continue
                except Exception:
                    pass
        else:
            tblist(controller, os.path.basename(tb))


def verify_incoming(ihier, verifylist):
    for controller in verifylist:
        ihier.add_controller(controller)
        direct_entries = glob.iglob(
            os.path.join(ihier.config.INCOMING, controller, "*")
        )
        tarball_dirs, unpacking_tarball_dirs = (list() for i in range(2))
        if not os.path.isdir(os.path.join(ihier.config.ARCHIVE, controller)):
            continue
        for dirent in direct_entries:
            dirt = os.path.basename(dirent)
            if (
                os.path.isdir(dirent)
                and not dirt.endswith(".unpack")
                and not len(os.listdir(dirent)) == 0
            ):
                tarball_dirs.append(dirt)
            elif (
                os.path.isdir(dirent)
                and not dirt.endswith(".unpack")
                and len(os.listdir(dirent)) == 0
            ):
                ihier.add_empty_tarball_dirs(controller, dirt)
            elif (
                os.path.isdir(dirent)
                and dirt.endswith(".unpack")
                and len(os.listdir(dirent)) == 0
            ):
                unpacking_tarball_dirs.append(dirt)
            elif os.path.islink(dirent):
                ihier.add_tarball_links(controller, dirt)

        if tarball_dirs:
            verify_tar_dirs(ihier, tarball_dirs, ihier.add_invalid_tb_dirs, controller)

        if unpacking_tarball_dirs:
            verify_tar_dirs(
                ihier,
                unpacking_tarball_dirs,
                ihier.add_invalid_unpacking_dirs,
                controller,
            )

    return 0


class ResultsHierarchy(object):
    def __init__(self, config):

        self.config = config
        self.controllers = list()
        self.results_check = {
            "res_empty_tarball_dirs": DictOfList(),
            "res_invalid_tb_links": DictOfList(),
            "res_incorrect_tb_dir_links": DictOfList(),
            "res_invalid_tb_dir_links": DictOfList(),
            "bad_prefixes": DictOfList(),
            "unused_prefix_files": DictOfList(),
            "missing_prefix_files": DictOfList(),
            "bad_prefix_files": DictOfList(),
            "unexpected_user_links": DictOfList(),
            "wrong_user_links": DictOfList(),
        }

    def add_controller(self, controller):
        self.controllers.append(controller)

    def add_res_empty_tarball_dirs(self, controller, tbdir):
        self.results_check["res_empty_tarball_dirs"].add_entry(controller, tbdir)

    def add_res_invalid_tb_links(self, controller, tbdir):
        self.results_check["res_invalid_tb_links"].add_entry(controller, tbdir)

    def add_res_incorrect_tb_dir_links(self, controller, tbdir):
        self.results_check["res_incorrect_tb_dir_links"].add_entry(controller, tbdir)

    def add_res_invalid_tb_dir_links(self, controller, tbdir):
        self.results_check["res_invalid_tb_dir_links"].add_entry(controller, tbdir)

    def add_bad_prefixes(self, controller, tbdir):
        self.results_check["bad_prefixes"].add_entry(controller, tbdir)

    def add_unused_prefix_files(self, controller, tbdir):
        self.results_check["unused_prefix_files"].add_entry(controller, tbdir)

    def add_missing_prefix_files(self, controller, tbdir):
        self.results_check["missing_prefix_files"].add_entry(controller, tbdir)

    def add_bad_prefix_files(self, controller, tbdir):
        self.results_check["bad_prefix_files"].add_entry(controller, tbdir)

    def add_unexpected_user_links(self, controller, tbdir):
        self.results_check["unexpected_user_links"].add_entry(controller, tbdir)

    def add_wrong_user_links(self, controller, tbdir):
        self.results_check["wrong_user_links"].add_entry(controller, tbdir)

    def dump(self, f, stat, hier=False):
        cnt = 0
        for verify_tardir in sorted(self.controllers):
            check = any(
                [
                    verify_tardir in self.results_check[k]._dict
                    for k in self.results_check
                ]
            )
            if check:
                cnt = 1
                if stat == 1:
                    header(f, "start", self.config.TS[4:], hier.name, hier.path)
                f.write(f"\nResults issues for controller: {verify_tardir}\n")
                if verify_tardir in self.results_check["res_empty_tarball_dirs"]._dict:
                    f.write("\tEmpty tar ball directories:\n")
                    self.output_format(f, verify_tardir, "res_empty_tarball_dirs")
                if verify_tardir in self.results_check["res_invalid_tb_links"]._dict:
                    f.write(
                        f"\tInvalid tar ball links (not in {self.config.ARCHIVE}):\n"
                    )
                    self.output_format(f, verify_tardir, "res_invalid_tb_links")
                if (
                    verify_tardir
                    in self.results_check["res_incorrect_tb_dir_links"]._dict
                ):
                    f.write("\tIncorrectly constructed tar ball links:\n")
                    self.output_format(f, verify_tardir, "res_incorrect_tb_dir_links")
                if (
                    verify_tardir
                    in self.results_check["res_invalid_tb_dir_links"]._dict
                ):
                    f.write("\tTar ball links to invalid incoming location:\n")
                    self.output_format(f, verify_tardir, "res_invalid_tb_dir_links")
                if verify_tardir in self.results_check["unused_prefix_files"]._dict:
                    f.write("\tTar ball links with unused prefix files:\n")
                    self.output_format(f, verify_tardir, "unused_prefix_files")
                if verify_tardir in self.results_check["missing_prefix_files"]._dict:
                    f.write("\tTar ball links with missing prefix files:\n")
                    self.output_format(f, verify_tardir, "missing_prefix_files")
                if verify_tardir in self.results_check["bad_prefix_files"]._dict:
                    f.write("\tTar ball links with bad prefix files:\n")
                    self.output_format(f, verify_tardir, "bad_prefix_files")
                if verify_tardir in self.results_check["bad_prefixes"]._dict:
                    f.write("\tTar ball links with bad prefixes:\n")
                    self.output_format(f, verify_tardir, "bad_prefixes")
                if verify_tardir in self.results_check["unexpected_user_links"]._dict:
                    f.write("\tTar ball links not configured for this user:\n")
                    self.output_format(f, verify_tardir, "unexpected_user_links")
                if verify_tardir in self.results_check["wrong_user_links"]._dict:
                    f.write("\tTar ball links for the wrong user:\n")
                    self.output_format(f, verify_tardir, "wrong_user_links")
                if stat == 1:
                    header(f, "end", self.config.TS[4:], hier.name, hier.path)

        return cnt

    def output_format(self, f, verify_tardir, dir_val):
        for val in sorted(self.results_check[dir_val]._dict[verify_tardir]):
            f.write(f"\t\t{val}\n")
        return 0


def verify_user_arg(rhier, mdlogcfg, user_arg, controler, path):
    user = ""
    try:
        user = mdlogcfg.get("run", "user")
    except NoSectionError:
        pass
    except NoOptionError:
        pass
    if not user:
        rhier.add_unexpected_user_links(controler, path)
    elif user_arg != user:
        rhier.add_wrong_user_links(controler, path)

    return


def verify_results(rhier, hier, user_arg=False):
    if user_arg:
        results_hierarchy = os.path.join(rhier.config.USERS, user_arg)
    else:
        results_hierarchy = hier.path

    for controller in hier.verifylist:
        tarball_dirs, unpacking_tarball_dirs = (list() for i in range(2))
        if not os.path.isdir(os.path.join(rhier.config.ARCHIVE, controller)):
            continue

        dirent_entries = list()
        for root, dirs, files in os.walk(
            os.path.join(results_hierarchy, controller), topdown=True
        ):
            for name in files:
                dirent_entries.append(os.path.join(root, name))
            for name in dirs:
                dirent_entries.append(os.path.join(root, name))

        if user_arg:
            controler = f"{user_arg}/{controller}"
            rhier.add_controller(controler)
        else:
            rhier.add_controller(controller)

        for dirent in dirent_entries:
            base_dir = os.path.basename(dirent)
            path = dirent.split(os.path.join(controller, ""), 1)[1]
            if os.path.isdir(dirent) and len(os.listdir(dirent)) == 0:
                if user_arg:
                    rhier.add_res_empty_tarball_dirs(controler, path)
                else:
                    rhier.add_res_empty_tarball_dirs(controller, path)
            elif os.path.islink(dirent):
                link = os.path.realpath(dirent)
                tb = f"{os.path.basename(path)}.tar.xz"
                incoming_path = os.path.join(
                    rhier.config.INCOMING, controller, base_dir
                )
                if not os.path.exists(
                    os.path.join(rhier.config.ARCHIVE, controller, tb)
                ):
                    rhier.add_res_invalid_tb_links(controller, base_dir)
                else:
                    if link != incoming_path:
                        rhier.add_res_incorrect_tb_dir_links(controller, base_dir)
                    elif not os.path.isdir(incoming_path) and not os.path.islink(
                        incoming_path
                    ):
                        rhier.add_res_invalid_tb_dir_links(controller, base_dir)
                    else:
                        prefix_path = os.path.dirname(path)
                        prefix_file = os.path.join(
                            rhier.config.ARCHIVE, controller, ".prefix", base_dir
                        )
                        prefix_file = f"{prefix_file}.prefix"
                        mdlogcfg = PbenchMDLogConfig(
                            os.path.join(incoming_path, "metadata.log")
                        )
                        prefix = ""
                        try:
                            prefix = mdlogcfg.get("run", "prefix")
                        except NoSectionError:
                            pass
                        except NoOptionError:
                            pass
                        if prefix_path == "":
                            if prefix:
                                rhier.add_bad_prefixes(controller, path)
                            elif os.path.exists(prefix_file):
                                rhier.add_unused_prefix_files(controller, path)
                        else:
                            if prefix:
                                if prefix != prefix_path:
                                    rhier.add_bad_prefixes(controller, path)
                            elif not os.path.exists(prefix_file):
                                rhier.add_missing_prefix_files(controller, path)
                            else:
                                f = 0
                                try:
                                    with open(prefix_file, "r") as file:
                                        prefix = file.read().replace("\n", "")
                                except Exception:
                                    f = 1
                                    pass
                                if f == 1:
                                    rhier.add_bad_prefix_files(controller, path)
                                else:
                                    if prefix != prefix_path:
                                        rhier.add_bad_prefixes(controller, path)
                        if user_arg:
                            verify_user_arg(rhier, mdlogcfg, user_arg, controler, path)

    return


class UserHierarchy(Hierarchy):
    def __init__(self, name, path, config):
        super().__init__(name, path, config)

        self.user_dir = list()
        self.unexpected_objects = list()

    def add_unexpected_objects(self, user):
        self.unexpected_objects.append(user)

    def add_user_dir(self, user):
        self.user_dir.append(user)

    def dump(self, f, hier, uhier):
        cnt = 0
        if self.unexpected_objects:
            header(f, "start", self.config.TS[4:], self.name, self.path)
            f.write("\nUnexpected files found:\n")
            for controller in sorted(self.unexpected_objects):
                f.write(f"\t{controller}\n")
            cnt = cnt + 1
            if self.user_dir:
                cnt += hier.dump(f, 0)
            header(f, "end", self.config.TS[4:], self.name, self.path)
        else:
            if self.user_dir:
                cnt += hier.dump(f, 1, uhier)

        return cnt


def verify_users(rhier, chier, hier):
    cnt = 0
    users = hier.path

    if not os.path.isdir(users):
        print(
            "The setting for USERS in the config file is {}, but that is"
            " not a directory",
            users,
        )
        return 1

    users_dirs = glob.iglob(os.path.join(users, "*"))
    user_dir = list()

    for user in users_dirs:
        u = os.path.basename(user)
        if os.path.isdir(user):
            user_dir.append(user)
            hier.add_user_dir(u)
        else:
            hier.add_unexpected_objects(u)

    if user_dir:
        for user in user_dir:
            verify_controllers(rhier, chier, user)
            if cnt > 0:
                cnt = cnt + 1

    return


def check_func(name, pbdirname):
    pbdir = name
    pbdir_p = os.path.realpath(pbdir)

    if not pbdir_p:
        print(f"{_NAME_}: Bad {pbdirname}={pbdir}", file=sys.stderr)
        return 1

    if not os.path.isdir(pbdir_p):
        print(f"{_NAME_}: Bad {pbdirname}={pbdir}", file=sys.stderr)
        return 1

    return 0


def main():
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        print(
            "{}: ERROR: No config file specified; set CONFIG env variable or"
            " use --config <file> on the command line".format(_NAME_),
            file=sys.stderr,
        )
        return 2

    try:
        config = PbenchConfig(cfg_name)
    except BadConfig as e:
        print("{}: {} (config file {})".format(_NAME_, e, cfg_name), file=sys.stderr)
        return 1

    if check_func(config.ARCHIVE, "ARCHIVE") > 0:
        return 1

    if check_func(config.INCOMING, "INCOMING") > 0:
        return 1

    if check_func(config.RESULTS, "RESULTS") > 0:
        return 1

    if check_func(config.USERS, "USERS") > 0:
        return 1

    logger = get_pbench_logger(_NAME_, config)

    ret = 0

    try:
        os.mkdir(os.path.join(config.LOGSDIR, "pbench-audit-server"))
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
        cnt = ahier.dump(f)
        if cnt > 0:
            ret += 1

        ihier = IncomingHierarchy(config)
        cihier = ControllerHierarchy("incoming", config.INCOMING, config)
        verify_controllers(ihier, cihier, config.INCOMING)
        cnt = cihier.dump(f, ihier, cihier)
        if cnt > 0:
            ret += 1

        rhier = ResultsHierarchy(config)
        crhier = ControllerHierarchy("results", config.RESULTS, config)
        verify_controllers(rhier, crhier, config.RESULTS)
        cnt = crhier.dump(f, rhier, crhier)
        if cnt > 0:
            ret += 1

        ruhier = ResultsHierarchy(config)
        cuhier = ControllerHierarchy("results", config.RESULTS, config)
        uhier = UserHierarchy("users", config.USERS, config)
        verify_users(ruhier, cuhier, uhier)
        cnt = uhier.dump(f, ruhier, uhier)
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
