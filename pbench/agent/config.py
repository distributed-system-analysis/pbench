import configparser

from pbench.common.exception import BadConfig


class PbenchAgentConfig(object):
    def __init__(self, cfg_name):
        self.conf = configparser.ConfigParser()
        self.conf.read(cfg_name)

    def get_pbench_run_dir(self):
        run_dir = self.conf.get("pbench-agent", "pbench_run")
        if not run_dir:
            run_dir = "/var/lib/pbench-agent"
        return run_dir

    def get_pbench_install_dir(self):
        install_dir = self.conf.get("pbench-agent", "install-dir")
        if not install_dir:
            raise BadConfig
        return install_dir

    def get_pbench_user(self):
        pbench_user = self.conf.get("pbench-agent", "pbench_user")
        if not pbench_user:
            return "pbench"
        return pbench_user

    def get_pbench_group(self):
        pbench_group = self.conf.get("pbench-agent", "pbench_group")
        if not pbench_group:
            return "pbench"
        return pbench_group
