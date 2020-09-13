from pbench.agent.base import BaseCommand
from pbench.agent.tools.clear import ClearMixIn

class ToolCommand(BaseCommand, ClearMixIn):
    def __init__(self, context):
        super(ToolCommand, self).__init__(context)