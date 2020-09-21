import glob
import os
from pathlib import Path
import shutil

import sh

from pbench.agent.utils import run_command
from pbench.agent.base import BaseCommand
from pbench.agent.sysinfo.collect import CollectMixIn


class SysinfoCommand(BaseCommand, CollectMixIn):
    def __init__(self, context):
        super(SysinfoCommand, self).__init__(context)

        # array containing all the possible sysinfo options
        self.sysinfo_opts_default = [
            "block",
            "libvirt",
            "kernel_config",
            "security_mitigations",
            "sos",
            "topology",
        ]
        self.sysinfo_opts_available = [
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

        # get comma separated values
        self.sysinfo_opts_default_comma_separated = ",".join(self.sysinfo_opts_default)
        self.sysinfo_opts_available_comma_separated = ",".join(
            self.sysinfo_opts_available
        )

        self.sysinfo = {
            "kernel_config": self.collect_kernel_config,
            "security_mitigations": self.collect_mitigation_data,
            "libvirt": self.collect_libvirt,
            "topology": self.collect_topology,
            "sos": self.collect_sos,
            "ara": self.collect_ara_data,
            "stockpile": self.collect_stockpile_data,
            "insights": self.collect_insights_data,
            "block": self.collect_block,
        }

    def collect_kernel_config(self):
        config = Path(f"/boot/config-{os.uname()[2]}")
        if config.exists():
            shutil.copy(config, self.sysinfo_path)

    def collect_mitigation_data(self):
        output = open("{}/security-mitigation-data.txt".format(self.sysinfo_path), "a")
        sh.grep(
            "-H",
            "-s",
            ".",
            glob.glob("/sys/devices/system/cpu/vulnerabilities/*"),
            _out=output,
        )
        try:
            sh.grep(
                "-H",
                "-s",
                ".",
                glob.glob("/sys/kernel/debug/x86/*enabled"),
                _out=output,
            )
        except sh.ErrorReturnCode_2:
            pass

    def collect_libvirt(self):
        libvirt_log = Path("/var/log/libvirt")
        if libvirt_log.exists():
            libvirt_results = self.sysinfo_path / "libvirt" / "log"
            libvirt_results.mkdir(parents=True)
            sh.sudo.cp("-r", "-p", str(libvirt_log), str(libvirt_results))
        libvirt_etc = Path("/etc/libvirt")
        if libvirt_etc.exists():
            libvirt_results = self.sysinfo_path / "libvirt" / "etc"
            libvirt_results.mkdir(parents=True)
            sh.sudo.cp("-r", "-p", str(libvirt_etc), str(libvirt_results))

    def collect_topology(self):
        self.sysinfo_path = self.sysinfo_path / "lstopo.txt"
        f = open(self.sysinfo_path, "w")
        run_command(sh.Command("lstopo"), "--of", "txt", out=f)

    def collect_sos(self):
        raise NotImplementedError

    def collect_ara_data(self):
        raise NotImplementedError

    def collect_stockpile_data(self):
        raise NotImplementedError

    def collect_insights_data(self):
        raise NotImplementedError

    def collect_block(self):
        raise NotImplementedError
