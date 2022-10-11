import os
from pathlib import Path
import re
import shutil
from typing import Iterable


class BadToolGroup(Exception):
    """Exception representing a tool group that does not exist or is invalid."""

    pass


class ToolGroup:
    """Provides an in-memory representation of the registered tools as recorded
    on-disk.
    """

    # Current tool group prefix in use.
    TOOL_GROUP_PREFIX = "tools-v1"

    @staticmethod
    def verify_tool_group(name: str, pbench_run: str = None) -> Path:
        """verify_tool_group - given a tool group name, verify it exists in the
        ${pbench_run} directory as a properly prefixed tool group directory
        name.

        Raises a BadToolGroup exception if the directory is invalid or does not
        exist, or if the pbench_run argument is None and the environment
        variable of the same name is missing.

        Returns a Pathlib object of the tool group directory on success.
        """
        _pbench_run = os.environ.get("pbench_run") if pbench_run is None else pbench_run
        if not _pbench_run:
            raise BadToolGroup(
                f"Cannot validate tool group, '{name}', 'pbench_run'"
                " environment variable missing"
            )

        tg_dir_name = Path(_pbench_run, f"{ToolGroup.TOOL_GROUP_PREFIX}-{name}")
        try:
            tg_dir = tg_dir_name.resolve(strict=True)
        except FileNotFoundError:
            raise BadToolGroup(
                f"Bad tool group, '{name}': directory {tg_dir_name} does not exist"
            )
        except Exception as exc:
            raise BadToolGroup(
                f"Bad tool group, '{name}': error resolving {tg_dir_name} directory"
            ) from exc
        else:
            if not tg_dir.is_dir():
                raise BadToolGroup(
                    f"Bad tool group, '{name}': directory {tg_dir_name} not valid"
                )
            else:
                return tg_dir

    def __init__(self, name: str, pbench_run: str = None):
        """Construct a ToolGroup object from the on-disk data of the given
        tool group.

        If the given tool group name is valid, the contents are read into the three
        dictionary structures:

          "toolnames" - each tool name is the key, with separate dictionaries
          for each registered host

          "hostnames" - each registered host is the key, with separate
          dictionaries for each tool registered on that host

          "labels" - each registered host name, that has a label, is the key,
          and the label is the value; if a host is not labeled, it does not
          show up in this dictionary

        Raises BadToolGroup via the verify_tool_group() method on error.
        """
        self.tg_dir = ToolGroup.verify_tool_group(name, pbench_run)
        self.name = name

        # __trigger__
        try:
            _trigger = (self.tg_dir / "__trigger__").read_text()
        except FileNotFoundError:
            # Ignore missing trigger file
            self.trigger = None
        else:
            if len(_trigger) == 0:
                # Ignore empty trigger file contents
                self.trigger = None
            else:
                self.trigger = _trigger

        # toolnames - Dict with tool name as the key, dictionary with host
        # names and parameters for each host
        self.toolnames = {}
        # hostnames - Dict with host name as the key, dictionary with tool
        # names and parameters for each tool
        self.hostnames = {}
        self.labels = {}
        for hdirent in os.listdir(self.tg_dir):
            if hdirent == "__trigger__":
                # Ignore handled above
                continue
            if not (self.tg_dir / hdirent).is_dir():
                # Ignore wayward non-directory files
                continue
            # We assume this directory is a hostname.
            host = hdirent
            assert (
                host not in self.hostnames
            ), f"Logic error!  {host} in {self.hostnames!r}"
            self.hostnames[host] = {}
            for tdirent in os.listdir(self.tg_dir / host):
                if tdirent == "__label__":
                    self.labels[host] = (
                        (self.tg_dir / host / tdirent).read_text().strip()
                    )
                    continue
                if tdirent.endswith("__noinstall__"):
                    # FIXME: ignore "noinstall" for now, tools are going to be
                    # in containers so this does not make sense going forward.
                    continue
                # This directory entry is the name of a tool.
                tool = tdirent
                tool_opts_text = (self.tg_dir / host / tool).read_text().strip()
                tool_opts = re.sub(r"\n\s*", " ", tool_opts_text)
                if tool not in self.toolnames:
                    self.toolnames[tool] = {}
                self.toolnames[tool][host] = tool_opts
                assert (
                    tool not in self.hostnames[host]
                ), f"Logic error!  {tool} in {self.hostnames[host]!r}"
                self.hostnames[host][tool] = tool_opts

    def get_tools(self, host):
        """get_tools - given a target host, return a dictionary with the list
        of tool names as keys, and the values being their options for that
        host.
        """
        tools = dict()
        for tool, opts in self.toolnames.items():
            try:
                host_opts = opts[host]
            except KeyError:
                # This host does not have this tool registered, ignore.
                pass
            else:
                tools[tool] = host_opts
        return tools

    def get_label(self, host):
        """get_label - given a target host, return the label associated with
        that host.
        """
        return self.labels.get(host, "")

    def archive(self, target_dir: Path):
        """Copy the entire tool group on-disk state to the target directory.
        No interpretation is applied.

        This is intentionally a convenience layer around shutil.copytree.

        For example:

            obj.tg_dir = "/a/b/tools-v1-red"
            target_dir = "/d/e/target_dir"

            obj.archive(target_dir)

            $ diff -r /a/b/tools-v1-red /d/e/target_dir/tools-v1-red
            $ echo ${?}
            0
        """
        shutil.copytree(str(self.tg_dir), target_dir / self.tg_dir.name, symlinks=False)


def gen_tool_groups(pbench_run: str) -> Iterable[ToolGroup]:
    """Generate a series of ToolGroup objects for each on-disk tool group
    found in the given pbench run directory.
    """
    for tg_dir in Path(pbench_run).glob(f"{ToolGroup.TOOL_GROUP_PREFIX}-*"):
        # All on-disk tool group directories will have names that look like
        # above, where the prefix also contains a '-'.  To strip the prefix,
        # we split the string and use the last component of the split.
        yield ToolGroup(tg_dir.name.split("-", 2)[2], pbench_run)
