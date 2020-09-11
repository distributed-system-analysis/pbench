from pbench.agent.base import BaseCommand
from pbench.agent.triggers.list import ListMixIn

class TriggerCommand(BaseCommand, ListMixIn):
    def __init__(self, context):
        super(TriggerCommand, self).__init__(context)
