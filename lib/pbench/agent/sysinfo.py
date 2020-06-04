import os
import pathlib
import shutil
import socket
import sys

import sh

from pbench.agent.logger import logger
from pbench.agent.config import AgentConfig
from pbench.agent.tools import Tools
from pbench.agent.utils import init_wrapper

SYSINFO_OPTS_AVAILABLE = [
    "block",
    "libvirt",
    "kernel_config",
    "security_mitigations",
    "sos",
    "topology",
    "ara",
    "stockpile",
    "insights",
]

SYSINFO_OPTS_DEFAULT = [
    "block",
    "libvirt",
    "kernel_config",
    "security_mitigations",
    "sos",
    "topology",
]


class Sysinfo:
    def __init__(self, group=None, sysinfo_dir=None, sysinfo=None, label=None):
        self.config = AgentConfig()
        if sysinfo == "all":
            sysinfo = ",".join(SYSINFO_OPTS_AVAILABLE)
        if sysinfo == "default":
            sysinfo = ",".join(SYSINFO_OPTS_DEFAULT)
        self.sysinfo = sysinfo
        if sysinfo_dir:
            self.sysinfo_dir = pathlib.Path(sysinfo_dir)
        self.group = group
        self.label = label
        self.tools = Tools()

        init_wrapper()

    def check(self):
        logger.debug("sysinfo_option is set to %s", self.sysinfo)
        if self.sysinfo in ["all", "default", "none"]:
            pass
        else:
            for item in self.sysinfo.split(","):
                if item in SYSINFO_OPTS_AVAILABLE:
                    continue
                else:
                    if item in ["all", "default", "none"]:
                        pass  # ignore these options
                    else:
                        logger.error("invalid sysinfo option: %s", item)
                        sys.exit(1)

    def collect(self, name):
        if name is None:
            logger.error(
                "Missing argument, need a name for this sysinfo"
                " collection, either 'beg' or 'end'"
            )
            sys.exit(1)
        if name not in ["beg", "end"]:
            logger.error(
                "Invalid argument, collection names should be either"
                "'beg' or 'end' not %s",
                name,
            )
            sys.exit(1)

        (sysnfo_path, tool_group_dir) = self._create_sysinfo_dir(name)

        for group in self.tools.groups:
            self.dump(name)

    def show_options(self):
        logger.info("default none all " + ", ".join(SYSINFO_OPTS_AVAILABLE))

    def dump(self, name):
        sysinfo_path = pathlib.Path(self.sysinfo_dir, socket.gethostname(), name)
        for item in self.sysinfo.split(","):
            logger.debug("Collecting %s", item)
            if item == "kernel_config":
                self._collect_kernel_config(sysinfo_path)
            elif item == "security_mitigations":
                self._collect_mitigation_data(sysinfo_path)
            elif item == "libvirt":
                self._collect_libvirt(sysinfo_path)
            elif item == "topology":
                self._collect_topology(sysinfo_path)
            elif item == "block":
                self._collect_block(sysinfo_path)
            else:
                logger.error("bad sysinfo value: %s", item)
                sys.exit(1)
        sh.contrib.sudo.chown("-R", 775, sysinfo_path)

    def _create_sysinfo_dir(self, name):
        self.sysinfo_dir.mkdir(parents=True, exist_ok=True)
        if not self.sysinfo_dir.exists():
            logger.error("Unable to create working directory, %s", self.sysinfo_dir)

            sys.exit(1)

        logger.info("Collecting sysinfo information")
        tool_group_dir = pathlib.Path(self.config.rundir, f"tools-{self.group}")
        if not tool_group_dir.exists():
            logger.error("Unble to find defult tools group file: %s", tool_group_dir)
            sys.exit(1)

        sysinfo_path = pathlib.Path(self.sysinfo_dir, socket.gethostname(), name)
        try:
            sysinfo_path.mkdir(parents=True)
        except FileExistsError:
            logger.error(
                "Already collection sysinfo-dump data, named: %s" " skipping...", name
            )
            sys.exit(0)

        return (sysinfo_path, tool_group_dir)

    def _collect_kernel_config(self, sysinfo_path):
        try:
            shutil.copy(f"/boot/config-{os.uname().release}", sysinfo_path)
        except Exception as ex:
            logger.error("Failed to copy kernel config: %s", ex)

    def _collect_mitigation_data(self, sysinfo_path):
        cpu_dir = pathlib.Path("/sys/devices/system/cpu/vulnerabilities")
        results = pathlib.Path(sysinfo_path, "security-mitigations.txt")
        if cpu_dir.exists():
            sh.grep(
                "-Hs",
                ".",
                sh.glob("/sys/devices/system/cpu/vulnerabilities/*"),
                _out=str(results),
            )
        try:
            f = open(results, "a+")
            sh.contrib.sudo.grep(
                "-Hs", ".", sh.glob("/sys/kernel/debug/x86/*enabled"), _out=f
            )
        except sh.ErrorReturnCode:
            # not enabled so ignore it, (at least on centos8)
            pass

    def _collect_libvirt(self, sysinfo_path):
        conf_results = pathlib.Path(sysinfo_path, "libvirt", "etc")
        conf_results.mkdir(parents=True, exist_ok=True)
        logs_results = pathlib.Path(sysinfo_path, "libvirt", "etc")
        logs_results.mkdir(parents=True, exist_ok=True)
        libvirt_conf = pathlib.Path("/etc/libvirt")
        libvirt_logs = pathlib.Path("/var/log/libvirt")
        if libvirt_conf.exists() and libvirt_logs.exists():
            sh.contrib.sudo.cp("-rp", libvirt_conf, conf_results)
            sh.contrib.sudo.cp("-rp", libvirt_logs, logs_results)

    def _collect_topology(self, sysinfo_path):
        try:
            lstopo = sh.Command("lstopo")
            result = pathlib.Path(sysinfo_path, "lstopo.txt")
            lstopo("--of", "txt", _out=str(result))
        except Exception:
            pass

    def _collect_block(self, sysinfo_path):
        try:
            block = pathlib.Path("/sys/block")
            results = open(pathlib.Path(sysinfo_path, "block_params.log"), "a+")
            if block.exists():
                for f in block.rglob("[s,h,v]d*/*"):
                    if f.is_file():
                        sh.echo(f, _out=results)
                        sh.cat(f, _out=results)
        except Exception:
            pass
