from pbench.agent.base import BaseCommand
from pbench.agent.meister.client import ClientMixIn
from pbench.agent.meister.meister import MeisterMixIn
from pbench.agent.meister.start import StartMixIn
from pbench.agent.meister.stop import StopMixIn


class MeisterCommand(BaseCommand, ClientMixIn, MeisterMixIn, StartMixIn, StopMixIn):
    def __init__(self, context):
        super(MeisterCommand, self).__init__(context)

        # Port number is "One Tool" in hex 0x170011
        self.redis_port = 17001

        self.channel = "tool-meister-chan"
