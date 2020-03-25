import os

import configparser

from pbench.lib import configtools
from pbench.agent import util

class PbenchAgentConfig(object):
    def __init__(self, cfg_name):
        # Enumerate the lisf ot files
        config_files = configtools.file_list(cfg_name)
        config_files.reverse()
        self.conf = configparser.ConfigParser()
       
    @property
    @util.lru_cache
    def get_pbench_run_dir(self):
        run_dir = self.conf.get('pbench-agent', 'pbench-run')
        if  not os.path.exists(run_dir):
            run_dir = "/var/lib/pbench-agent"
        return run_dir

    def _get(self, *args, **kwargs):
        return self.conf.get(*args, **kwargs)
