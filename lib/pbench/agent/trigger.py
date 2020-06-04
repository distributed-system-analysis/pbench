import fileinput
import pathlib
import sys

from pbench.agent.logger import logger
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

    def register(self, group, start_trigger, stop_trigger):
        """Regiester a trigger"""
        if ":" in start_trigger:
            logger.error(
                "The start tigger cannot have a colon in it: %s", start_trigger
            )
            sys.exit(1)

        if ":" in stop_trigger:
            logger.error("The stop tigger cannot have a colon in it: %s", stop_trigger)
            sys.exit(1)
        if self.trigger.exists():
            for line in fileinput.input(files=str(self.trigger), inplace=1):
                if line.startswith(group):
                    line = line.replace(line, "")
                print(line, end="")
        f = open(self.trigger, "a")
        f.write(f"{group}:{start_trigger}:{stop_trigger}\n")
        logger.info(
            "tool trigger strings for start: %s and stop: %s are now " "registerd",
            start_trigger,
            stop_trigger,
        )
