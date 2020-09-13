from pbench.agent.base import BaseCommand
from pbench.agent.config import ConfigMixIn

class ConfigCommand(BaseCommand, ConfigMixIn):
    def __init__(self, context):
        super(ConfigCommand, self).__init__(context)