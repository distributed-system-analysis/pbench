import pathlib
import os
import sys

import sh

from pbench.agent.logger import logger
from pbench.agent.utils import init_wrapper
from pbench.agent.config import AgentConfig


class Tools:
    def __init__(self):
        self.config = AgentConfig()
        self.rundir = pathlib.Path(self.config.rundir)
        self.installdir = pathlib.Path(self.config.installdir)

        # look for pbench agent tools in the configuration file first before
        # looking for the local directory
        self.toolsdir = pathlib.Path(self.config.installdir, "tool-scripts")
        if not self.toolsdir.exists():
            self.toolsdir = os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                "../../../agent/tool-scripts",
            )

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

    def list(self, name=None, group=None):
        def _groups(group):
            return [p.name for p in self.rundir.glob(f"tools-{group}/*")]

        def _print(label, results):
            if len(results) != 0:
                print("%s: %s" % (label, ", ".join(results)))

        if name and group:
            logger.error("You cannot specify both group and name")
            sys.exit(1)

        if self.rundir.exists():
            if name:
                _print(
                    name,
                    [
                        p.parent.name.split("tools-")[1]
                        for p in self.rundir.rglob(f"tools-*/{name}")
                    ],
                )
            elif group:
                if self.verify_tool_group(group):
                    _print(
                        group, [p.name for p in self.rundir.rglob(f"tools-{group}/*")]
                    )
            elif group is None and name is None:
                if len(self.groups) == 0:
                    sys.exit(1)

                for group in self.groups:
                    print("%s: %s" % (group, ", ".join(_groups(group))))

    def register(self, name, labels_args, group, install, test_label, args):
        def _install_tool(name, args):
            try:
                cmd = ["--install"]
                tool = pathlib.Path(self.installdir, f"tool-scripts/{name}")
                if not tool.exists():
                    # used for unit tests
                    tool = pathlib.Path(
                        os.path.join(
                            os.path.dirname(os.path.realpath(__file__)),
                            "../../../agent/tool-scripts",
                        ),
                        name,
                    )
                name = sh.Command(tool)
                if args:
                    cmd.append(args)
                result = name(cmd)
                if result != "":
                    logger.info(result.stdout.strip().decode("utf-8"))
            except sh.CommandNotFound:
                logger.error(
                    "Could not find %s in %s: has this tool been "
                    "integrated into pbench-agent?",
                    name,
                    self.toolsdir,
                )
                sys.exit(1)
            except sh.ErrorReturnCode as ex:
                logger.error(
                    "Failed to execute %s %s:\n%s",
                    name,
                    " ".join(cmd),
                    ex.stderr.strip().decode("utf-8"),
                )
                sys.exit(1)

        if name is None:
            logger.error("Missing required parameter --name")
            sys.exit(1)

        if install:
            _install_tool(name, args)
            tool_group_dir = pathlib.Path(self.rundir, f"tools-{group}")
            tool_group_dir.mkdir(parents=True, exist_ok=True)
            tool_file = pathlib.Path(self.rundir, f"tools-{group}/{name}")
            if tool_file.exists():
                tool_file.unlink()
            tool_file.touch()
            if args:
                with open(tool_file, "w+") as f:
                    f.write(args)
            logger.info("%s tool is now registered in group %s", name, group)
        else:
            logger.error("Failed to install too %s", name)
