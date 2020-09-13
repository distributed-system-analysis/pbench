from pbench.agent.base import BaseCommand
from pbench.agent.config import ConfigMixIn
from pbench.agent.config import SSHMixIn

class ConfigCommand(BaseCommand, ConfigMixIn, SSHMixIn):
    def __init__(self, context):
        super(ConfigCommand, self).__init__(context)