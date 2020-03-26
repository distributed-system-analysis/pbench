import configparser


class PbenchAgentConfig(object):
    def __init__(self, cfg_name):
        self.conf = configparser.ConfigParser()
        self.conf.read(cfg_name)

    def get_pbench_run_dir(self):
        run_dir = self.conf.get("pbench-agent", "pbench_run")
        if not run_dir:
            run_dir = "/var/lib/pbench-agent"
        return run_dir
