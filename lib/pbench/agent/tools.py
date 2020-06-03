import pathlib
import sys

from pbench.agent.utils import init_wrapper
from pbench.agent.config import AgentConfig


class Tools:
    def __init__(self):
        self.config = AgentConfig()
        self.rundir = pathlib.Path(self.config.rundir)
        self.installdir = pathlib.Path(self.config.installdir)
        self.toolsdir = pathlib.Path(self.config.installdir, "tool-scripts")

        init_wrapper()

    @property
    def groups(self):
        return [p.name.split("tools-")[1] for p in self.rundir.glob("tools-*")]

    def registered(self, group):
        """List of all registered tools"""
        return [p for p in self.rundir.rglob(f"tools-{group}/*")]

    def verify_tool_group(self, group):
        """Verify that tool exists"""
        return group in self.groups

    def clear(self, name, group):
        """Remove tools that have been registered

        :param name: Tool that is registered
        :param group: Group for the tool to be removed from
        """
        # if no tool is specified delete everything
        if name is None:
            name = "*"

        tool_group_dir = self.rundir / f"tools-{group}"
        if not tool_group_dir.exists():
            sys.exit(1)

        try:
            for p in tool_group_dir.glob(name):
                p.unlink()
        except FileNotFoundError:
            # If the tool doesnt exist in the group silently ignore it
            pass
