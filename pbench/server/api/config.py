import os
import sys

from pbench import PbenchConfig
from pbench.common.exceptions import BadConfig


class ServerConfig:
    def __init__(self):
        self.cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
        if not self.cfg_name:
            print("{}: ERROR: No config file specified; set CONFIG".format(__name__))
            sys.exit(1)
        self.pbench_config = None
        self.server = None

    def get_pbench_config(self):
        if not self.pbench_config:
            try:
                self.pbench_config = PbenchConfig(self.cfg_name)
            except BadConfig as e:
                print(
                    "{}: {} (config file {})".format(__name__, e, self.cfg_name),
                    file=sys.stderr,
                )
                sys.exit(1)
        return self.pbench_config

    def get_server_config(self):
        pc = self.get_pbench_config()
        self.server = pc.conf["pbench-server"]
        return self.server
