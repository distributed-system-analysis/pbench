from pbench.agent.base import BaseCommand
from pbench.agent.triggers.list import ListMixIn
from pbench.agent.triggers.register import RegisterMixIn

class TriggerCommand(BaseCommand, ListMixIn, RegisterMixIn):
    def __init__(self, context):
        super(TriggerCommand, self).__init__(context)
