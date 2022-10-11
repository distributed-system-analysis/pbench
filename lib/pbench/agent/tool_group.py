import errno
import os
from pathlib import Path
import re
import shutil
from typing import Any, Dict, Iterable, Optional

import filelock

from pbench.agent.utils import LocalRemoteHost


class BadToolGroup(Exception):
    """Exception representing a tool group that does not exist or is invalid."""

    pass


class HostNotFound(Exception):
    """Exception representing a host not found in a tool group on-disk
    structure.
    """

    pass


class ToolNotFound(Exception):
    """Exception representing a tool not found in a tool group on-disk
    structure.
    """

    pass


class BadStartTrigger(Exception):
    """Exception for a start trigger containing a colon, not a string, or an
    empty string.
    """

    pass


class BadStopTrigger(Exception):
    """Exception for a stop trigger containing a colon, not a string, or an
    empty string.
    """

    pass


class ToolGroup:
    """Provides an in-memory representation of the registered tools as recorded
    on-disk.

    The public interfaces are:

        Class Attributes:

            TOOL_GROUP_PREFIX: constant for the on-disk tool group prefix

        Static Methods:
            verify_tool_group(): verify a given tool group name exists

        Class Methods:
            gen_tool_groups(): generate a list of ToolGroup objects from disk

        Object Methods:
            trigger():          return registered trigger
            toolnames():        return dictionary mapping tool to hosts
            hostnames():        return dictionary mapping host to tools
            labels():           return dictionary mapping host to label
            get_tools():        return a list of tools for a host
            get_label():        return a label for a host
            archive():          archive the on-disk tool group structure
            store_trigger():    write a new tool trigger to disk
            unregister_tool():  unregister a tool for the given host
            unregister_host():  unregister all tools for the given host
    """

    # Current tool group prefix in use.
    TOOL_GROUP_PREFIX = "tools-v1"

    _LOCK_FILE_SUFFIX = "lock"
    _TRIGGER_FILE_NAME = "__trigger__"
    _LABEL_FILE_NAME = "__label__"
    _NOINSTALL_SUFFIX = "__noinstall__"

    @staticmethod
    def verify_tool_group(name: str, pbench_run: Optional[str] = None) -> Path:
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

    @classmethod
    def gen_tool_groups(cls, pbench_run: str) -> Iterable[Any]:
        """Generate a series of ToolGroup objects for each on-disk tool group
        found in the given pbench run directory.
        """
        for tg_dir in Path(pbench_run).glob(f"{ToolGroup.TOOL_GROUP_PREFIX}-*"):
            # All on-disk tool group directories will have names that look like
            # above.
            yield cls(tg_dir.name[len(ToolGroup.TOOL_GROUP_PREFIX) + 1 :], pbench_run)

    def __init__(self, name: str, pbench_run: Optional[str] = None):
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
        self.tg_dir = self.verify_tool_group(name, pbench_run)
        self.name = name

        self._trigger = None
        # toolnames - Dict with tool name as the key, dictionary with host
        # names and parameters for each host
        self._toolnames: Dict[str, Dict[str, str]] = {}
        # hostnames - Dict with host name as the key, dictionary with tool
        # names and parameters for each tool
        self._hostnames: Dict[str, Dict[str, str]] = {}
        self._labels: Dict[str, str] = {}

        lockfile = self.tg_dir.parent / f".{self.tg_dir.name}.{self._LOCK_FILE_SUFFIX}"
        self._lockfile = filelock.UnixFileLock(str(lockfile), timeout=10)

        # Perform the actual on-disk load into memory.
        with self._lockfile.acquire():
            self._do_load()

        # By default, our in-memory state is "clean", unknown if it matches
        # the on-disk state.
        self._dirty = False

    def _do_load(self):
        """Internal load from disk, assumes nothing about in-memory state.
        The contructor and load() method are responsible.
        """
        for hdirent in self.tg_dir.iterdir():
            if hdirent.name == self._TRIGGER_FILE_NAME:
                _trigger = hdirent.read_text()
                if len(_trigger) > 0:
                    self._trigger = _trigger
                continue
            if not hdirent.is_dir():
                # Ignore wayward non-directory files
                continue
            # We assume this directory is a hostname.
            host = hdirent
            assert (
                host.name not in self._hostnames
            ), f"Logic error!  {host.name} in {self._hostnames!r}"
            self._hostnames[host.name] = {}
            for tdirent in host.iterdir():
                if tdirent.name == self._LABEL_FILE_NAME:
                    self._labels[host.name] = tdirent.read_text().strip()
                    continue
                if tdirent.name.endswith(self._NOINSTALL_SUFFIX):
                    # FIXME: ignore "noinstall" for now, tools are going to be
                    # in containers so this does not make sense going forward.
                    continue
                # This directory entry is the name of a tool.
                tool = tdirent
                tool_opts_text = tool.read_text().strip()
                tool_opts = re.sub(r"\n\s*", " ", tool_opts_text)
                if tool.name not in self._toolnames:
                    self._toolnames[tool.name] = {}
                self._toolnames[tool.name][host.name] = tool_opts
                assert (
                    tool.name not in self._hostnames[host.name]
                ), f"Logic error!  {tool.name} in {self._hostnames[host.name]!r}"
                self._hostnames[host.name][tool.name] = tool_opts

    def _load(self):
        """Load, or reload, on-disk state into memory.  The dirty flag is
        cleared if previously set.

        NOTE: The operation of reading the on-disk state is NOT atomic.

        FIXME: We could use a lock file during the load and the
        register/unregister changes to make that a reality.
        """
        if not self._dirty:
            return

        self._trigger = None
        self._toolnames = dict()
        self._hostnames = dict()
        self._labels = dict()

        with self._lockfile.acquire():
            self._do_load()

        # In-memory state cleanly loaded from disk.
        self._dirty = False

    def is_empty(self) -> bool:
        """Determine if a tool group is empty."""
        if self._trigger or self._hostnames:
            return True
        assert not self._toolnames, "Logic error: have tool names but no host names"
        return False

    def trigger(self) -> Optional[str]:
        """Return the registered tool trigger, if any."""
        self._load()
        return self._trigger

    def toolnames(self) -> Dict[str, Dict[str, str]]:
        """Return the dictionary mapping tool to hosts on which it is registered."""
        self._load()
        return self._toolnames

    def hostnames(self) -> Dict[str, Dict[str, str]]:
        """Return the dictionary mapping host to tools registered for it."""
        self._load()
        return self._hostnames

    def labels(self) -> Dict[str, str]:
        """Return the dictionary mapping host to label."""
        self._load()
        return self._labels

    def verify_hostnames(self):
        """verify all registered host names properly resolve their host
        information.
        """
        lr = LocalRemoteHost()
        for host in self.hostnames:
            try:
                lr.resolve(host)
            except Exception as exc:
                raise BadToolGroup(
                    f"Bad tool group, '{self.name}': '{host}' did not resolve"
                ) from exc

    def get_tools(self, host: str) -> Dict[str, str]:
        """get_tools - given a target host, return a dictionary with the list
        of tool names as keys, and the values being their options for that
        host.
        """
        self._load()

        tools = dict()
        for tool, opts in self._toolnames.items():
            try:
                host_opts = opts[host]
            except KeyError:
                # This host does not have this tool registered, ignore.
                pass
            else:
                tools[tool] = host_opts
        return tools

    def get_label(self, host: str) -> str:
        """get_label - given a target host, return the label associated with
        that host.
        """
        self._load()

        return self._labels.get(host, "")

    def archive(self, target_dir: Path) -> None:
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
        with self._lockfile.acquire():
            shutil.copytree(
                str(self.tg_dir),
                target_dir / self.tg_dir.name,
                symlinks=False,
            )

    def store_trigger(self, start: str, stop: str) -> None:
        """Store the start and stop triggers."""
        if not isinstance(start, str) or not start or ":" in start:
            raise BadStartTrigger()
        if not isinstance(stop, str) or not stop or ":" in stop:
            raise BadStopTrigger()
        with self._lockfile.acquire():
            trigger_f = self.tg_dir / self._TRIGGER_FILE_NAME
            trigger_f.write_text(f"{start}:{stop}\n")
            self._dirty = True

    def _remove_group_ondisk(self) -> None:
        """Remove a custom (non-default) tool group directory if it has no
        tools registered.

        No error is raised if the directory still has contents.
        """
        if self.name == "default":
            return
        try:
            self.tg_dir.rmdir()
        except OSError as exc:
            if exc.errno != errno.ENOTEMPTY:
                raise

    def unregister_tool(self, host: str, tool: str) -> None:
        """Unregister a tool for a given host.

        Also updates the objects in-memory copy of the on-disk state.

        Returns 0 on success, 1 on error.
        """
        with self._lockfile.acquire():
            hpath = self.tg_dir / host
            tpath = hpath / tool

            try:
                # Unregister the tool from the given host.
                tpath.unlink()
            except FileNotFoundError:
                raise ToolNotFound(host, tool)
            else:
                # The in-memory state is now dirty.
                self._dirty = True

            noinstall = tpath.parent / f"{tpath.name}.{self._NOINSTALL_SUFFIX}"
            try:
                # Remove an associated no-install file.
                noinstall.unlink()
            except FileNotFoundError:
                pass
            except Exception as exc:
                raise BadToolGroup(f"Failed to remove internal state: {exc}")

            try:
                # Remove the potentially empty host directory, as the
                # unregistered tool could have been the last one for this
                # host.
                hpath.rmdir()
            except OSError as exc:
                if exc.errno == errno.ENOTEMPTY:
                    # Still has tools in it, ignore.
                    pass
                else:
                    raise BadToolGroup(f"Failed removing host directory {hpath}: {exc}")
            else:
                # Try to clean-up an empty tool group, since a host was
                # removed.
                self._remove_group_ondisk()

    def unregister_host(self, host: str) -> None:
        """Unregister all tools for a given host.

        The entire on-disk state of the group will be removed if there are no
        hosts or triggers registered.

        Raises HostNotFound if the host is not registered in the on-disk state
        of this group.
        """
        with self._lockfile.acquire():
            try:
                hpath = (self.tg_dir / host).resolve(strict=True)
            except FileNotFoundError:
                raise HostNotFound(host)
            else:
                # Regardless of how far the directory tree removal gets,
                # consider the in-memory state dirty.
                self._dirty = True
                shutil.rmtree(str(hpath))
                # Try to clean-up an empty tool group since a host was
                # removed.
                self._remove_group_ondisk()
