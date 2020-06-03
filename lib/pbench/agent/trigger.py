import pathlib

from pbench.agent.config import AgentConfig
from pbench.agent.tools import Tools


class Trigger:
    def __init__(self):
        self.config = AgentConfig()
        self.tools = Tools()
        self.rundir = pathlib.Path(self.config.rundir)
        self.trigger = pathlib.Path(self.rundir, "tool-triggers")

    def list(self, group):
        """List the triggers available
        :param group: group to search triggers for
        """
        if self.rundir.exists():
            if group is None:
                group = self.tools.groups
            for grp in group:
                with open(self.trigger, "r") as f:
                    for d in f:
                        if d.startswith(grp):
                            print(d.strip())
