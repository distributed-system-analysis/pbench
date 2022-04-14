#!/usr/bin/env python3
# -*- mode: python -*-

"""pbench-tool-meister

Handles the life-cycle executing a given tool on a host. The Tool Meister
performs the following operations:

  1. Ensures the given tool exists with the supported version
  2. Fetches the parameters configured for the tool
  3. Waits for the message to start the tool
     a. Messages contain three pieces of information:
        the next operational state to move to, the tool group being for which
        the operation will be applied, and the directory in which the Tool
        Data Sink will collect and store all the tool data during send
        operations
  4. Waits for the message to stop the tool
  5. Waits for the message to send the tool data remotely
  6. Repeats steps 3 - 5 until a "terminate" message is received

If a SIGTERM or SIGQUIT signal is sent to the Tool Meister, any existing
running tool is shutdown, all local data is removed, and the Tool Meister
exits.

A redis [1] instance is used as the communication mechanism between the
various Tool Meisters on nodes and the benchmark driver. The redis instance is
used both to communicate the initial data set describing the tools to use, and
their parameteres, for each Tool Meister, as well as a pub/sub for
coordinating starts and stops of all the tools.

The Tool Meister is given two arguments when started: the redis server to use,
and the redis key to fetch its configuration from for its operation.

[1] https://redis.io/
"""

import errno
import hashlib
import io
import json
import logging
import logging.handlers
import os
import requests
import requests.exceptions
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List, NamedTuple, Tuple

from daemon import DaemonContext
from pathlib import Path
import pidfile
import redis

from pbench.agent.constants import (
    tm_allowed_actions,
    tm_channel_suffix_to_tms,
    tm_channel_suffix_from_tms,
    tm_channel_suffix_to_logging,
    TDS_RETRY_PERIOD_SECS,
)
from pbench.agent.redis_utils import (
    RedisHandler,
    RedisChannelSubscriber,
    wait_for_conn_and_key,
)
from pbench.agent.toolmetadata import ToolMetadata
from pbench.agent.utils import collect_local_info
from pbench.common.utils import md5sum


# Logging format string for unit tests
fmtstr_ut = "%(levelname)s %(name)s %(funcName)s -- %(message)s"
fmtstr = "%(asctime)s %(levelname)s %(process)s %(thread)s %(name)s %(funcName)s %(lineno)d -- %(message)s"


def log_raw_io_output(iob: io.IOBase, logger: logging.Logger):
    """Thread start function to log raw output from a given IOBase object."""
    for line in iob.readlines():
        _log_line = line.decode("utf-8").strip()
        if _log_line:
            logger.info(_log_line)


class ToolException(Exception):
    """ToolException - Exception class for all exceptions raised by the Tool
    class object methods.
    """

    pass


class InstallationResult(NamedTuple):
    returncode: int
    output: str


class Tool:
    """Encapsulates all the state needed to manage a tool running as a background
    process.

    The ToolMeister class uses one Tool object per running tool.

    This base class provides for constructing an object with the required
    parameters, ensuring the pbench installation directory and tool directory
    exist.

    The four abstract methods, install, start, stop, and wait, are defined, and
    two helper methods are provided for waiting on processes.
    """

    _tool_type = None

    def __init__(
        self,
        name: str,
        tool_opts: str,
        pbench_install_dir: Path,
        logger: logging.Logger,
    ):
        """Generic Tool constructor storing the tool name, its invocation
        options, the pbench installation directory, and a logger object to
        use.

        Raises a ToolException if the pbench installation directory does not
        exist.
        """
        self.name = name
        self.tool_opts = tool_opts
        if not pbench_install_dir.is_dir():
            raise ToolException(
                f"pbench installation directory does not exist: {pbench_install_dir}"
            )
        self.pbench_install_dir = pbench_install_dir
        self.logger = logger

    def install(self) -> InstallationResult:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the install method"
        )

    def start(self, tool_dir: Path):
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the start method"
        )

    def stop(self):
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the stop method"
        )

    def wait(self):
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the wait method"
        )

    def _create_process_with_logger(
        self, args: list, cwd: Path, ctx: str = None
    ) -> subprocess.Popen:
        """Generic method of creating a sub-process with a thread to capture
        stdout/stderr and log it.
        """
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        _ctx = f"-{ctx}" if ctx else ""
        process_logger = threading.Thread(
            target=log_raw_io_output,
            args=(
                process.stdout,
                self.logger.getChild(f"logger{_ctx}"),
            ),
        )
        process_logger.daemon = True
        process_logger.start()
        return process

    def _wait_for_process(self, process: subprocess.Popen, ctx_name: str = None) -> int:
        """Generic method to wait for a given process to stop after 30
        seconds, emitting a message every 5 seconds in between.

        Returns the process return code on success, or None if the process
        failed to exit.
        """
        count = 6
        sts = None
        while count > 0 and sts is None:
            try:
                sts = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                count -= 1
                if count > 0:
                    self.logger.debug(
                        "%s tool %s%s has not stopped after %d seconds",
                        self._tool_type,
                        self.name,
                        f" {ctx_name}" if ctx_name else "",
                        5 * (6 - count),
                    )
        return sts

    def _wait_for_process_with_kill(
        self, process: subprocess.Popen, ctx_name: str = None
    ):
        """Generic method of waiting for a given process, killing the process
        if the initial wait failed, waiting a second time for the kill to take
        effect.
        """
        _ctx_name = f" {ctx_name}" if ctx_name else ""
        self.logger.info(
            "Waiting for %s tool %s%s process", self._tool_type, self.name, _ctx_name
        )
        # We wait for the {ctx_name} process to finish first ...
        sts = self._wait_for_process(process, ctx_name)
        if sts is None:
            # The {ctx_name} process did not terminate gracefully, so we bring
            # out the big guns ...
            process.kill()
            self.logger.error(
                "Killed un-responsive %s tool %s%s process",
                self._tool_type,
                self.name,
                _ctx_name,
            )
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.logger.warning(
                    "Killed %s tool %s%s process STILL didn't die after waiting another 30 seconds, closing its FDs",
                    self._tool_type,
                    self.name,
                    _ctx_name,
                )
                process.stdin.close()
                process.stdout.close()
                process.stderr.close()
        elif sts != 0 and sts != -(signal.SIGTERM):
            self.logger.warning(
                "%s tool %s%s process failed with %d",
                self._tool_type,
                self.name,
                _ctx_name,
                sts,
            )


class TransientTool(Tool):
    """Encapsulates handling of most transient tools."""

    _tool_type = "Transient"

    def __init__(self, name: str, tool_opts: str, **kwargs):
        """Transient Tool constructor which adds the specific tool script, the
        start and stop process tracking fields, and the current tool directory
        in use.
        """
        super().__init__(name, tool_opts, **kwargs)
        self.tool_script = f"{self.pbench_install_dir}/tool-scripts/{self.name}"
        self.start_process = None
        self.stop_process = None
        self.tool_dir = None

    def install(self) -> InstallationResult:
        """Synchronously runs the tool --install mode capturing the return code and
        output, returning them as a tuple to the caller.
        """
        args = [
            self.tool_script,
            "--install",
            self.tool_opts,
        ]
        cp = subprocess.run(
            args,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        return InstallationResult(returncode=cp.returncode, output=cp.stdout.strip())

    def start(self, tool_dir: Path):
        """Creates the background process running the tool's "start" operation.

        Arguments:

            tool_dir:  the directory in which to create the transient tool's
                       working directory.

        Raises a ToolException if the given tool directory does not exist.
        """
        if not tool_dir.is_dir():
            raise ToolException(f"tool directory does not exist: {tool_dir!r}")
        assert self.tool_dir is None, f"tool directory already defined: {self.tool_dir}"
        assert (
            self.start_process is None
        ), f"Tool({self.name}) has an unexpected start process running"
        assert (
            self.stop_process is None
        ), f"Tool({self.name}) has an unexpected stop process running"

        args = [
            self.tool_script,
            "--start",
            f"--dir={tool_dir}",
            self.tool_opts,
        ]
        self.logger.info("%s: start_tool -- %s", self.name, " ".join(args))
        self.start_process = self._create_process_with_logger(args, tool_dir, "start")
        self.tool_dir = tool_dir

    def stop(self):
        """Stops the background process by running the tool's "stop" operation."""
        assert self.tool_dir is not None, f"tool directory not defined: {self.tool_dir}"
        assert (
            self.start_process is not None
        ), f"Tool({self.name})'s start process not running"
        assert (
            self.stop_process is None
        ), f"Tool({self.name}) has an unexpected stop process running"

        # Before we "stop" a tool, check to see if a "{tool}/{tool}.pid" file
        # exists.  If it doesn't, wait for a second for it to show up.  If
        # after a second it does not show up, then give up waiting and just call
        # the stop method.
        tool_pid_file = self.tool_dir / self.name / f"{self.name}.pid"
        cnt = 100
        while not tool_pid_file.exists():
            cnt -= 1
            if cnt <= 0:
                self.logger.warning(
                    "Tool(%s) pid file, %s, does not exist after waiting 10 seconds",
                    self.name,
                    tool_pid_file,
                )
                break
            time.sleep(0.1)

        args = [
            self.tool_script,
            "--stop",
            f"--dir={self.tool_dir}",
            self.tool_opts,
        ]
        self.logger.info("%s: stop_tool -- %s", self.name, " ".join(args))
        self.stop_process = self._create_process_with_logger(
            args, self.tool_dir, "stop"
        )
        self.tool_dir = None

    def wait(self):
        """Wait for any tool processes to terminate after a "stop" process has
        completed.

        Waits for the tool's "stop" process to complete, if started, then
        waits for the tool's start process to complete (since the "stop"
        process is supposed stop the "start" process).
        """
        assert self.tool_dir is None, "Logic bomb!  tool directory still provided!"
        assert (
            self.stop_process is not None
        ), f"Tool({self.name}) does not have a stop process running"
        assert (
            self.start_process is not None
        ), f"Tool({self.name}) does not have a start process running"

        # First wait for the "stop" process to do it's job ...
        self._wait_for_process_with_kill(self.stop_process, "stop")
        self.stop_process = None
        # ... then we wait for the start process to finish; in either case,
        # we'll only wait a short time before killing them.
        self._wait_for_process_with_kill(self.start_process, "start")
        self.start_process = None


class PcpTransientTool(Tool):
    """The transient tool alternative to the PCP persistent tool, which starts
    and stops both a pmcd and pmlogger process, and sends data remotely, as
    directed for transient tools.
    """

    _tool_type = "Transient"

    def __init__(self, name: str, tool_opts: str, **kwargs):
        """PCP Transient Tool constructor which adds the path and process
        fields for the pmcd and pmlogger processes.
        """
        super().__init__(name, tool_opts, **kwargs)
        self.pmcd_path = None
        self.pmcd_process = None
        self.pmlogger_path = None
        self.pmlogger_process = None

    def install(self) -> InstallationResult:
        """Installation check for the PCP Transient Tool.

        Both the pmcd and pmlogger commands need to exist to be considered
        successful, unlike the PCP Persistent Tool which only runs the pmcd
        command.

        Responsible for recording the paths to both the pmcd and pmlogger
        commands.
        """
        self.pmcd_path = shutil.which("pmcd")
        if not self.pmcd_path:
            return InstallationResult(returncode=1, output="pcp tool (pmcd) not found")
        self.pmlogger_path = shutil.which("pmlogger")
        if not self.pmlogger_path:
            return InstallationResult(
                returncode=1, output="pcp tool (pmlogger) not found"
            )
        return InstallationResult(
            returncode=0, output="pcp tool (pmcd and pmlogger) properly installed"
        )

    def start(self, tool_dir: Path):
        """Start the PCP transient tool sub-processes, the pmcd process and
        the pmlogger process.

        Arguments:

            tool_dir:  the directory in which to create the PCP transient
                       tool's working directory.

        Raises a ToolException if the given tool directory does not exist.
        """
        if not tool_dir.is_dir():
            raise ToolException(f"tool directory does not exist: {tool_dir!r}")
        assert self.pmcd_path is not None, "Path to pmcd not provided"
        assert self.pmlogger_path is not None, "Path to pmlogger not provided"
        assert (
            self.pmcd_process is None
        ), f"Tool({self.name}) has an unexpected pmcd process running"
        assert (
            self.pmlogger_process is None
        ), f"Tool({self.name}) has an unexpected pmlogger process running"

        _tool_dir = tool_dir / self.name.replace("-transient", "")
        pmcd_args = [
            self.pmcd_path,
            "--foreground",
            "--socket=./pmcd.socket",
            "--port=55677",
            f"--config={self.pbench_install_dir}/templates/pmcd.conf",
        ]
        pmlogger_args = [
            self.pmlogger_path,
            "--log=-",
            "--report",
            "-t",
            "3s",
            "-c",
            f"{self.pbench_install_dir}/templates/pmlogger.conf",
            "--host=localhost:55677",
            f"{_tool_dir}/%Y%m%d.%H.%M",
        ]

        self.logger.info(
            "%s: start_tool -- '%s' && '%s'",
            self.name,
            " ".join(pmcd_args),
            " ".join(pmlogger_args),
        )
        self.pmcd_process = self._create_process_with_logger(
            pmcd_args, _tool_dir, "pmcd"
        )
        self.pmlogger_process = self._create_process_with_logger(
            pmlogger_args, _tool_dir, "pmlogger"
        )

    def stop(self):
        """Stop the pmcd and pmlogger processes."""
        assert (
            self.pmcd_process is not None
        ), f"Tool({self.name}) the expected pmcd process is not running"
        assert (
            self.pmlogger_process is not None
        ), f"Tool({self.name}) the expected pmlogger process is not running"

        self.logger.info("%s: stop_tool", self.name)
        try:
            self.pmlogger_process.terminate()
        except Exception:
            self.logger.exception(
                "Failed to terminate pmlogger ('%s')", self.pmlogger_process.args
            )
        try:
            self.pmcd_process.terminate()
        except Exception:
            self.logger.exception(
                "Failed to terminate pmcd ('%s')", self.pmcd_process.args
            )

    def wait(self):
        """Wait for the pmcd and pmlogger processes to stop executing."""
        assert (
            self.pmcd_process is not None
        ), f"Tool({self.name}) the expected pmcd process is not running"
        assert (
            self.pmlogger_process is not None
        ), f"Tool({self.name}) the expected pmlogger process is not running"

        self._wait_for_process_with_kill(self.pmcd_process, "pmcd")
        self.pmcd_process = None
        self._wait_for_process_with_kill(self.pmlogger_process, "pmlogger")
        self.pmlogger_process = None


class PersistentTool(Tool):
    """PersistentTool - Encapsulates all the states needed to run persistent
    tooling in the background.  A PersistentTool extends the base Tool class
    with some simple modifications for stopping the tool without the need for
    an external stop script.

    Each persistent tool extends this intermediate "base" class with its
    own particular behaviors.
    """

    _tool_type = "Persistent"

    def __init__(self, name: str, tool_opts: str, **kwargs):
        """PersistentTool objects add an "args" field to the object, filled in
        by the specific persistent tool's ".install()" method, and the process
        field tracking the process created by the ".start()" method.
        """
        super().__init__(name, tool_opts, **kwargs)
        self.args = None
        self.process = None

    def start(self, tool_dir: Path):
        """Start the persistent tool sub-process.

        Arguments:

            tool_dir:  the directory in which to create the specific persistent
                       tool's working directory.

        Raises a ToolException if the given tool directory does not exist.
        """
        if not tool_dir.is_dir():
            raise ToolException(f"tool directory does not exist: {tool_dir!r}")
        assert self.args is not None, "Logic bomb!  {self.name} install had failed!"
        assert (
            self.process is None
        ), f"Tool({self.name}) has an unexpected process running"

        _tool_dir = tool_dir / self.name
        _tool_dir.mkdir()

        self.logger.debug("Starting persistent tool %s, args %r", self.name, self.args)
        self.process = self._create_process_with_logger(self.args, _tool_dir, "start")
        self.logger.info("Started persistent tool %s, %r", self.name, self.args)

    def stop(self):
        """Terminate the persistent tool sub-process.

        This method does not wait for the process to actually exit. The caller
        should issue a wait() for that.
        """
        assert (
            self.process is not None
        ), f"Tool({self.name}) does not have a process running"

        try:
            self.process.terminate()
        except Exception:
            self.logger.exception("Failed to terminate %s (%r)", self.name, self.args)
        else:
            self.logger.info("Terminate issued for persistent tool %s", self.name)

    def wait(self):
        """Wait for the persistent tool to exit.

        Requires the caller to issue a stop() first.
        """
        assert (
            self.process is not None
        ), f"Tool({self.name}) does not have a process running"

        self._wait_for_process_with_kill(self.process)
        self.process = None


class DcgmTool(PersistentTool):
    """DcgmTool - provide specific persistent tool behaviors for the "dcgm"
    tool.
    """

    def install(self) -> InstallationResult:
        """Installation check for the dcgm-exporter tool.

        Responsible for recording the shell arguments for running
        dcgm-exporter.
        """
        executable = shutil.which("dcgm-exporter")
        if executable is None:
            return InstallationResult(
                returncode=1, output="dcgm tool (dcgm-exporter) not found"
            )
        self.args = [executable]
        return InstallationResult(
            returncode=0, output="dcgm tool (dcgm-exporter) properly installed"
        )


class NodeExporterTool(PersistentTool):
    """NodeExporterTool - provide specifics for running the "node-exporter"
    tool.
    """

    def install(self) -> InstallationResult:
        """Installation check for the node_exporter tool.

        Responsible for recording the shell arguments for running
        node_exporter.
        """
        executable = shutil.which("node_exporter")
        if executable is None:
            return InstallationResult(
                returncode=1, output="node_exporter tool not found"
            )
        self.args = [executable]
        return InstallationResult(
            returncode=0, output="node_exporter tool properly installed"
        )


class PcpTool(PersistentTool):
    """PcpTool - provide specifics for running the "pcp" tool, which is really
    the "pmcd" process.
    """

    def install(self) -> InstallationResult:
        """Installation check for the PCP Persistent tool.

        Responsible for recording the shell arguments for running PCP pmcd
        command.
        """
        executable = shutil.which("pmcd")
        if executable is None:
            return InstallationResult(returncode=1, output="pcp tool (pmcd) not found")
        # FIXME - The Tool Data Sink and Tool Meister have to agree on the
        # exact port number to use.  We can't use the default `pmcd` port
        # number because it might conflict with an existing `pmcd`
        # deployment out of our control.
        self.args = [
            executable,
            "--foreground",
            "--socket=./pmcd.socket",
            "--port=55677",
            f"--config={self.pbench_install_dir}/templates/pmcd.conf",
        ]
        return InstallationResult(
            returncode=0, output="pcp tool (pmcd) properly installed"
        )


class ToolMeisterError(Exception):
    """Simple exception for any errors from the ToolMeister class."""

    pass


class ToolMeisterParams(NamedTuple):
    benchmark_run_dir: str
    channel_prefix: str
    tds_hostname: str
    tds_port: str
    controller: str
    group: str
    hostname: str
    label: str
    tool_metadata: ToolMetadata
    tools: Dict[str, str]


class ToolMeister:
    """Encapsulate tool life-cycle

    The goal of this class is to provide the methods and attributes necessary
    for managing the life-cycles of a registered set of tools.

    The start_, stop_, send_, and wait_ prefixed methods represent all the
    necessary interfaces for managing the life-cycle of a tool.  The cleanup()
    method is provided to abstract away any necessary clean up required by a
    tool so that the main() driver does not need to know any details about a
    tool.

    The format of the JSON data for the parameters is as follows:

        {
            "benchmark_run_dir":  "<Top-level directory of the current"
                          " benchmark run>",
            "channel_prefix":  "<Redis server channel prefix used to form"
                          " the to/from channel names used for receiving"
                          " actions and sending status>",
            "tds_hostname":  "<Tool Data Sink host name>",
            "tds_port":   "<Tool Data Sink port number in use>",
            "controller": "<hostname of the controller driving all the Tool"
                          " Meisters; if this Tool Meister is running locally"
                          " with the controller, then it does not need to send"
                          " data to the Tool Data Sink since it can access the"
                          " ${benchmark_run_dir} and ${benchmark_results_dir}"
                          " directories directly.>",
            "group":      "<Name of the tool group from which the following"
                          " tools data was pulled, passed as the"
                          " --group argument to the individual tools>",
            "hostname":   "<hostname of Tool Meister, should be same as"
                          " 'hostname -f' where Tool Meister is running>",
            "label":      "<Tool label applied to this Tool Meister host>",
            "tool_metadata":  "<Metadata about the nature of all tools>",
            "tools": {
                "tool-0": [ "--opt-0", "--opt-1", ..., "--opt-N" ],
                "tool-1": [ "--opt-0", "--opt-1", ..., "--opt-N" ],
                ...,
                "tool-N": [ "--opt-0", "--opt-1", ..., "--opt-N" ]
            }
        }

    Each action message should contain three pieces of data: the action to
    take, either start, stop, or send, the tool group to apply that action to,
    and the directory in which to store the data. In JSON form it will look
    like:

        {
            "action":    "<'sysinfo'|'init'|'start'|'stop'|'send'|'end'>",
            "group":     "<tool group name>",
            "directory": "<directory in which to store tool data>"
        }

    If the Tool Meister is running on the same host as the pbench agent
    controller, then the Tool Meister will write it's data directly to the
    ${benchmark_results_dir} using the controller's host name; if the Tool
    Meister is running remotely, then it will use a local temporary directory
    to write it's data, and will send that data to the Tool Data Sink during
    the "send" phase.
    """

    @staticmethod
    def fetch_params(params: Dict[str, Any]) -> ToolMeisterParams:
        """Static help method that allows the method constructing a ToolMeister
        instance to verify the parameters before we actually construct the
        object.

        The definition of the contents of a parameter block is really
        independent of a ToolMeister implementation, but we keep this method
        in the ToolMeister class since it is closely related to the
        implementation.
        """
        try:
            return ToolMeisterParams(
                benchmark_run_dir=params["benchmark_run_dir"],
                channel_prefix=params["channel_prefix"],
                tds_hostname=params["tds_hostname"],
                tds_port=params["tds_port"],
                controller=params["controller"],
                group=params["group"],
                hostname=params["hostname"],
                label=params["label"],
                tool_metadata=ToolMetadata.tool_md_from_dict(params["tool_metadata"]),
                tools=params["tools"],
            )
        except KeyError as exc:
            raise ToolMeisterError(f"Invalid parameter block, missing key {exc}")

    _valid_states = frozenset(["startup", "idle", "running", "shutdown"])
    _message_keys = frozenset(["action", "args", "directory", "group"])
    # Most tools we have today are "transient" tools, and are handled by external
    # scripts.  Our three persistent tools (and pcp-transient) are handled in the
    # code directly.
    #
    # FIXME - we should eventually allow them to be loaded externally.
    _tool_name_class_mappings = {
        "dcgm": DcgmTool,
        "node-exporter": NodeExporterTool,
        "pcp": PcpTool,
        "pcp-transient": PcpTransientTool,
    }

    def __init__(
        self,
        pbench_install_dir: Path,
        tmp_dir: Path,
        tar_path: str,
        sysinfo_dump: str,
        params: Dict[str, Any],
        redis_server: redis.Redis,
        logger: logging.Logger,
    ):
        """Constructor for the ToolMeister object - sets up the internal state
        given the constructor parameters, setting up the state transition
        table, and forming the various channel names from the channel prefix
        in the params object.
        """
        if not pbench_install_dir.is_dir():
            raise ToolMeisterError(
                f"pbench installation directory does not exist: {pbench_install_dir}"
            )
        self.pbench_install_dir = pbench_install_dir
        if not tmp_dir.is_dir():
            raise ToolMeisterError(f"temporary directory does not exist: {tmp_dir}")
        self._tmp_dir = tmp_dir
        self.tar_path = tar_path
        self.sysinfo_dump = sysinfo_dump
        self._params = self.fetch_params(params)
        self._rs = redis_server
        self.logger = logger
        self._usable_tools = dict()
        # No running tools at first
        self._running_tools = dict()
        # No transient tools at first
        self._transient_tools = dict()
        # No persistent tools at first
        self._persistent_tools = dict()
        self.persistent_tool_names = self._params.tool_metadata.getPersistentTools()
        for name in self.persistent_tool_names:
            assert (
                name in self._tool_name_class_mappings
            ), f"Logic bomb! {name} not in tool name class mappings"
        # We start in the "startup" state, waiting for first "init" action.
        self.state = "startup"

        # A series of operational "constants".
        self._state_trans = {
            "end": {"curr": "idle", "next": "shutdown", "action": self.end_tools},
            "init": {"curr": "startup", "next": "idle", "action": self.init_tools},
            "start": {"curr": "idle", "next": "running", "action": self.start_tools},
            "stop": {"curr": "running", "next": "idle", "action": self.stop_tools},
        }
        for key in self._state_trans.keys():
            assert (
                key in tm_allowed_actions
            ), f"INTERNAL ERROR: invalid state transition entry, '{key}'"
            assert self._state_trans[key]["next"] in self._valid_states, (
                "INTERNAL ERROR: invalid state transition 'next' entry for"
                f" '{key}', '{self._state_trans[key]['next']}'"
            )

        # Name of the channel on which this Tool Meister instance will listen.
        self._to_tms_channel = (
            f"{self._params.channel_prefix}-{tm_channel_suffix_to_tms}"
        )
        # Name of the channel on which all Tool Meister instances respond.
        self._from_tms_channel = (
            f"{self._params.channel_prefix}-{tm_channel_suffix_from_tms}"
        )

        # The current 'directory' into which the tools are collected; not set
        # until a 'start tools' is executed, cleared when a 'send tools'
        # completes.
        self._directory = None
        # The dictionary we use to track the directories which have not been
        # sent to the Tool Data Sink.
        self.directories = dict()
        # The "tool directory" is the current directory in use by running
        # tools for storing their collected data.
        self._tool_dir = None
        # The operational Redis channel the TDS will use to send actions to
        # the Tool Meisters, filled in later by the context manager.
        self._to_tms_chan = None

    def __enter__(self):
        """Enter context manager method - responsible for establishing the
        Tool Meister channel on which we'll receive operational instructions,
        collecting the local data and metadata about this Tool Meister
        instance, and sending our startup message to the Tool Data Sink.
        """
        self._to_tms_chan = RedisChannelSubscriber(
            self._rs, self._to_tms_channel, RedisChannelSubscriber.ONEOFMANY
        )

        version, seqno, sha1, hostdata = collect_local_info(self.pbench_install_dir)

        tool_installs = {}
        for name, tool_opts in sorted(self._params.tools.items()):
            tklass = self._tool_name_class_mappings.get(name, TransientTool)
            try:
                tool = tklass(
                    name,
                    tool_opts,
                    pbench_install_dir=self.pbench_install_dir,
                    logger=self.logger,
                )
                res = tool.install()
            except Exception:
                self.logger.exception("Failed to run tool %s install check", name)
                res = InstallationResult(returncode=-42, output="internal-error")
            # Record the result of the tool installation check so it can be
            # reported back to the Tool Data Sink.
            tool_installs[name] = res
            if res.returncode == 0:
                # Remember the successful Tool instances
                self._usable_tools[name] = tool_opts
                if name in self.persistent_tool_names:
                    self._persistent_tools[name] = tool
                else:
                    self._transient_tools[name] = tool

        started_msg = dict(
            hostname=self._params.hostname,
            kind="tm",
            label=self._params.label,
            pid=os.getpid(),
            version=version,
            seqno=seqno,
            sha1=sha1,
            hostdata=hostdata,
            installs=tool_installs,
        )

        # Tell the entity that started us who we are, indicating we're ready.
        self.logger.debug("publish %s", self._from_tms_channel)
        num_present = 0
        timeout = time.time() + TDS_RETRY_PERIOD_SECS
        while num_present == 0:
            try:
                num_present = self._rs.publish(
                    self._from_tms_channel, json.dumps(started_msg, sort_keys=True)
                )
            except redis.ConnectionError:
                num_present = 0
            if num_present == 0 and time.time() >= timeout:
                raise Exception(
                    f"Unable to publish startup ack message, {started_msg!r}"
                )
        self.logger.debug("published %s", self._from_tms_channel)
        return self

    def __exit__(self, *args):
        """Exit context manager method - close down the "to-tms" Redis channel,
        and send the final terminated status to the Tool Data Sink.
        """
        self.logger.info("%s: terminating", self._params.hostname)
        self._to_tms_chan.close()
        # Send the final "terminated" acknowledgement message.
        self._send_client_status("terminated")

    def _gen_data(self):
        """_gen_data - fetch and decode the JSON object off the "wire".

        The keys in the JSON object are validated against the expected keys,
        and the value of the 'action' key is validated against the list of
        actions.
        """
        for tmp_data in self._to_tms_chan.fetch_json(self.logger):
            data = None
            msg = None
            keys = frozenset(tmp_data.keys())
            if keys != self._message_keys:
                msg = f"unrecognized keys in data of payload in message, {tmp_data!r}"
            elif tmp_data["action"] not in tm_allowed_actions:
                msg = f"unrecognized action in data of payload in message, {tmp_data!r}"
            elif (
                tmp_data["group"] is not None
                and tmp_data["group"] != self._params.group
            ):
                msg = f"unrecognized group in data of payload in message, {tmp_data!r}"
            else:
                data = tmp_data
            if msg is not None:
                assert data is None, f"msg = {msg}, tmp_data = {tmp_data!r}"
                self.logger.warning(msg)
                self._send_client_status(msg)
            else:
                assert msg is None, f"msg = {msg}, tmp_data = {tmp_data!r}"
                yield data["action"], data

    def wait_for_command(self):
        """wait_for_command - wait for the expected data message for the
        current state

        Reads messages pulled from the wire, ignoring messages for unexpected
        actions, returning an (action_method, data) tuple when an expected
        state transition is encountered, and setting the next state properly.
        """
        self.logger.debug("%s: wait_for_command %s", self._params.hostname, self.state)
        for action, data in self._gen_data():
            if action == "terminate":
                self.logger.debug("%s: msg - %r", self._params.hostname, data)
                break
            if action == "send":
                yield self.send_tools, data
                continue
            if action == "sysinfo":
                yield self.sysinfo, data
                continue
            state_trans_rec = self._state_trans[action]
            if state_trans_rec["curr"] != self.state:
                msg = f"ignoring unexpected data, {data!r}, in state '{self.state}'"
                self.logger.warning(msg)
                self._send_client_status(msg)
                continue
            action_method = state_trans_rec["action"]
            self.state = state_trans_rec["next"]
            self.logger.debug("%s: msg - %r", self._params.hostname, data)
            yield action_method, data

    def _send_client_status(self, status: str) -> int:
        """_send_client_status - convenience method to properly publish a
        client operation status.

        Return 0 on success, 1 on failure, logging errors or exceptions
        encountered during its operation.
        """
        # The published client status message contains three pieces of
        # information:
        #   {
        #     "kind": "ds|tm",
        #     "hostname": "< the host name on which the ds or tm is running >",
        #     "status": "success|< a message to be displayed on error >"
        #   }
        msg_d = dict(kind="tm", hostname=self._params.hostname, status=status)
        msg = json.dumps(msg_d, sort_keys=True)
        self.logger.debug("publish %s %s", self._from_tms_channel, msg)
        try:
            num_present = self._rs.publish(self._from_tms_channel, msg)
        except redis.ConnectionError as exc:
            self.logger.error(
                "Failed to publish client status message, %r: %s", msg, exc
            )
            ret_val = 1
        except Exception:
            self.logger.exception("Failed to publish client status message, %r", msg)
            ret_val = 1
        else:
            if num_present != 1:
                self.logger.error(
                    "client status message %r received by %d subscribers",
                    msg,
                    num_present,
                )
                ret_val = 1
            else:
                if status != "terminated":
                    self.logger.debug("posted client status message, %r", msg)
                ret_val = 0
        return ret_val

    def _create_tool_directory(self, directory: str) -> Tuple[Path, Path]:
        """Create a temporary tool directory suitable for persistent or
        transient tool use.

        Arguments:

            directory:  the directory value provided by the "init" or "start"
                        tools message.

                        When the Tool Meister is run in a container the
                        "directory" parameter will not map into its namespace,
                        so we always consider containerized Tool Meisters as
                        remote.

        Returns a tuple of Path objects, one for a created parent temporary
        directory (None if not created), and one for the created tool
        directory.

        Raises a ToolException if the given directory is local and can't be
        resolved, or if a temporary directory can't be created.
        """
        local_dir = Path(directory)
        if self._params.controller == self._params.hostname and local_dir.exists():
            # The Tool Meister instance is running on the same host as the
            # controller (not in a container).  We just use the directory
            # given to us in the `start` message.
            base_dir = local_dir.resolve(strict=True)
            tmp_dir = None
        else:
            # The Tool Meister instance is running remotely from the
            # controller, or in a container.  A local temporary directory is
            # created instead of using the directory parameter.
            try:
                base_dir = Path(
                    tempfile.mkdtemp(
                        dir=self._tmp_dir,
                        prefix=f"tm.{self._params.group}.{os.getpid()}.",
                    )
                )
            except Exception as exc:
                raise ToolException(
                    "Failed to create a temporary directory for tools"
                ) from exc
            tmp_dir = base_dir
        if self._params.label:
            _sub_dir = f"{self._params.label}:{self._params.hostname}"
        else:
            _sub_dir = self._params.hostname
        tool_dir = base_dir / _sub_dir
        try:
            tool_dir.mkdir()
        except Exception as exc:
            raise ToolException(
                "Failed to create local tool directory, %s", tool_dir
            ) from exc
        return tmp_dir, tool_dir

    def _start_tools(
        self, tools_to_start: Dict[str, Tool], tool_dir: Path
    ) -> Dict[str, Tool]:
        """Invoke the .start() method for each Tool in the dictionary of tools
        to start.

        Arguments:

            tools_to_start:  dictionary of Tool objects to be started

        Returns a dictionary of all the tools successfully tarted.
        """
        started_tools = {}
        for name, tool in sorted(tools_to_start.items()):
            try:
                tool.start(tool_dir)
            except Exception:
                self.logger.exception(
                    "Failure starting tool %s running in background", name
                )
            else:
                started_tools[name] = tool
        return started_tools

    def init_tools(self, data: Dict[str, str]) -> int:
        """Setup all registered persistent tools which have data collectors.

        The Tool Data Sink will be setting up the actual processes which
        collect data from these tools.

        Arguments:

            data: a dictionary of the arguments sent to the Tool Meister

        Returns 0 on success, # of failures otherwise.
        """
        try:
            _tmp_dir, _tool_dir = self._create_tool_directory(data["directory"])
        except Exception:
            self.logger.exception(
                "Failed to create local tool directory for %s", data["directory"]
            )
            self._send_client_status("internal-error")
            return 1

        # Remember this persistent tmp tool directory so that we can delete it
        # when requested.
        self.directories[data["directory"]] = _tmp_dir if _tmp_dir else _tool_dir

        # Start all the persistent tools running.
        started_tools = self._start_tools(self._persistent_tools, _tool_dir)

        failures = len(self._persistent_tools) - len(started_tools)
        if failures > 0:
            tool_cnt = len(self._persistent_tools)
            msg = f"{failures} of {tool_cnt} persistent tools failed to start"
            self._send_client_status(msg)
        else:
            self._send_client_status("success")
        return failures

    def start_tools(self, data: Dict[str, str]) -> int:
        """Start all registered transient tools executing in the background.

        The 'action' and 'group' values of the payload have already been
        validated before this "start tools" action is invoked.

        If this Tool Meister instance is running on the same host as the
        controller, we'll use the given "directory" argument directly for
        where tools will store their collected data.  When this Tool Meister
        instance is remote, we'll use a temporary directory on that remote
        host.

        Arguments:

            data: a dictionary of the arguments sent to the Tool Meister

        Returns 0 on success, # of failures otherwise.
        """
        if self._running_tools or self._directory is not None:
            self.logger.error(
                "INTERNAL ERROR - encountered previously running tools, %r",
                self._running_tools,
            )
            self._send_client_status("internal-error")
            return 1

        try:
            _, self._tool_dir = self._create_tool_directory(data["directory"])
        except Exception:
            self.logger.exception(
                "Failed to create local tool directory for %s", data["directory"]
            )
            self._send_client_status("internal-error")
            return 1

        # Remember the tool directory for the future "send".
        self._directory = data["directory"]

        # Start all the transient tools running.
        self._running_tools = self._start_tools(self._transient_tools, self._tool_dir)

        failures = len(self._transient_tools) - len(self._running_tools)
        if failures > 0:
            tool_cnt = len(self._transient_tools)
            msg = f"{failures} of {tool_cnt} tools failed to start"
            self._send_client_status(msg)
        else:
            self._send_client_status("success")
        return failures

    def _wait_for_tools(self) -> int:
        """Convenience method to properly wait for all the currently running
        tools to finish before returning to the caller.

        Returns the # of failures encountered waiting for tools, logging any
        errors along the way.
        """
        failures = 0
        for name, tool in sorted(self._running_tools.items()):
            try:
                tool.wait()
            except Exception:
                self.logger.exception(
                    "Failed to wait for tool %s to stop running in background", name
                )
                failures += 1
        return failures

    def _stop_running_tools(self) -> int:
        """Convenience method to properly stop all the currently running tools
        before returning to the caller.

        Returns the # of failures encountered waiting for tools, logging any
        errors along the way.
        """
        failures = 0
        for name, tool in sorted(self._running_tools.items()):
            try:
                tool.stop()
            except Exception:
                self.logger.exception(
                    "Failed to stop tool %s running in background", name
                )
                failures += 1
        return failures

    def stop_tools(self, data: Dict[str, str]) -> int:
        """stop_tools - stop any running tools.

        The 'action' and 'group' values of the payload have already been
        validated before this "stop tools" action is invoked.

        This method only proceeds if the 'directory' entry value of the
        payload matches what was previously provided to a "start tools"
        action.

        Arguments:

            data: a dictionary of the arguments sent to the Tool Meister

        Returns 0 on success, # of failures otherwise.
        """
        if self._directory != data["directory"]:
            self.logger.error(
                "INTERNAL ERROR - stop tools action encountered for a"
                " directory, '%s', that is different from the previous"
                " start tools, '%s'",
                data["directory"],
                self._directory,
            )
            return 1

        tool_cnt = len(self._running_tools)
        failures = self._stop_running_tools()
        failures += self._wait_for_tools()

        # Clean up the running tools data structure explicitly ahead of
        # potentially receiving another start tools.
        if __debug__:
            _running_l = self._running_tools.keys()
            _running_fs = frozenset(_running_l)
            _transient_l = self._transient_tools.keys()
            _transient_fs = frozenset(_transient_l)
            if _running_fs - _transient_fs != frozenset():
                raise AssertionError(
                    f"The set of running tools, {sorted(_running_l)!r}, is not a"
                    f" sub-set of the transient tools, {sorted(_transient_l)!r}"
                )
        self._running_tools = dict()

        # Remember this tool directory so that we can send its data when
        # requested.
        self.directories[self._directory] = self._tool_dir
        self._directory = None
        self._tool_dir = None

        if failures > 0:
            msg = f"{failures} of {tool_cnt} failed stopping tools"
            self._send_client_status(msg)
        else:
            self._send_client_status("success")
        return failures

    def _create_tar(
        self,
        directory: Path,
        tar_file: Path,
    ) -> subprocess.CompletedProcess:
        """
        Creates a tar file at a given tar file path. This method invokes tar
        directly for efficiency.  If an error occurs, it will retry with all
        warnings suppressed.

        Arguments:

            directory:  a Path object describing the directory from which to
                        create the tar file
            tar_file:   the Path object describing where to create the tar file

        Returns the CompletedProcess object returned by subprocess.run.
        """

        def tar(tar_args: List):
            return subprocess.run(
                tar_args,
                cwd=directory.parent,
                stdin=None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

        tar_args = [
            self.tar_path,
            "--create",
            "--xz",
            "--force-local",
            f"--file={tar_file}",
            directory.name,
        ]

        cp = tar(tar_args)
        if cp.returncode != 0:
            self.logger.warning(
                "Tarball creation failed with %d (stdout '%s') on %s: Re-trying now.",
                cp.returncode,
                cp.stdout.decode("utf-8"),
                directory,
            )
            tar_args.insert(2, "--warning=none")
            cp = tar(tar_args)
            if cp.returncode != 0:
                self.logger.warning("Failed to create tarball, %s", cp.stdout)

        return cp

    def _send_directory(self, directory: Path, uri: str, ctx: str) -> int:
        """Tar up the given directory and send via PUT to the URL constructed
        from the "uri" fragment, using the provided context.

        Arguments:

            directory: a Path object with a `name` matching self._params.hostname or
                       {self._params.label}:{self._params.hostname}, referred to as the
                       target_dir.

            uri:       URL base path element for the PUT operation
            ctx:       Context element for the PUT URL

            The uri and ctx arguments are used to form the final URL as
            defined by:

                f"http://{self._params.controller}:8080/{uri}/{ctx}/{target_dir}"

        Returns 0 on success, # of failures otherwise.
        """
        if self._params.label:
            assert (
                directory.name == f"{self._params.label}:{self._params.hostname}"
            ), f"Expected directory target with <label>:<hostname>, '{directory}'"
        else:
            assert (
                directory.name == self._params.hostname
            ), f"Expected directory target with <hostname>, '{directory}'"

        failures = 0
        target_dir = directory.name
        parent_dir = directory.parent
        tar_file = parent_dir / f"{target_dir}.tar.xz"

        try:
            if self._create_tar(directory, tar_file).returncode != 0:
                # Tar ball creation failed even after suppressing all the warnings,
                # we will now proceed to create an empty tar ball.
                # TODO: it'd be better to be able to skip the PUT entirely if the
                # tar fails and simply log a failure without TDS waiting forever.
                if self._create_tar(Path("/dev/null"), tar_file).returncode != 0:
                    # Empty tarball creation failed, so we're going to skip the PUT
                    # operation.
                    raise ToolMeisterError(
                        f"Failed to create an empty tar {str(tar_file)}"
                    )
        except ToolMeisterError:
            raise
        except Exception:
            self.logger.exception(
                "Exception attempting to create the tarball, '%s'", tar_file
            )
            failures += 1
        else:
            try:
                (_, tar_md5) = md5sum(tar_file)
            except Exception:
                self.logger.exception(
                    "Exception on attempting to create an MD5 for the tarball, '%s'",
                    tar_file,
                )
                failures += 1
            else:
                self.logger.debug(
                    "%s: starting send_data group=%s, directory=%s",
                    self._params.hostname,
                    self._params.group,
                    self._directory,
                )
                headers = {"md5sum": tar_md5}
                url = (
                    f"http://{self._params.tds_hostname}:{self._params.tds_port}/{uri}"
                    f"/{ctx}/{self._params.hostname}"
                )
                sent = False
                retries = 200
                while not sent:
                    try:
                        with tar_file.open("rb") as tar_fp:
                            response = requests.put(url, headers=headers, data=tar_fp)
                    except (
                        ConnectionRefusedError,
                        requests.exceptions.ConnectionError,
                    ) as exc:
                        self.logger.debug("%s", exc)
                        # Try until we get a connection.
                        time.sleep(0.1)
                        retries -= 1
                        if retries <= 0:
                            raise
                    else:
                        sent = True
                        if response.status_code != 200:
                            self.logger.error(
                                "PUT '%s' failed with '%d', '%s'",
                                url,
                                response.status_code,
                                response.text,
                            )
                            failures += 1
                        else:
                            self.logger.debug(
                                "PUT '%s' succeeded ('%d', '%s')",
                                url,
                                response.status_code,
                                response.text,
                            )
                            try:
                                shutil.rmtree(parent_dir)
                            except Exception:
                                self.logger.exception(
                                    "Failed to remove tool data" " hierarchy, '%s'",
                                    parent_dir,
                                )
                                failures += 1
                self.logger.info(
                    "%s: PUT %s completed %s %s",
                    self._params.hostname,
                    uri,
                    self._params.group,
                    directory,
                )
        finally:
            # We always remove the created tar file regardless of success or
            # failure. The above code should take care of removing the
            # directory tree the tar file was created from when it was
            # successfully transferred, but if the transfer failed, we'll
            # still have the local directory, so the tar file is still
            # deletable.
            try:
                tar_file.unlink()
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    self.logger.warning(
                        "error removing tar ball, '%s': %s", tar_file, exc
                    )
            except Exception as exc:
                self.logger.warning(
                    "unexpected error removing tar ball, '%s': %s", tar_file, exc
                )
        return failures

    def send_tools(self, data: Dict[str, str]) -> int:
        """Send any collected tool data to the Tool Data Sink.

        The 'action' and 'group' values of the payload have already been
        validated before this "send tools" action is invoked.

        This method only proceeds if the 'directory' entry value of the
        payload matches what was previously provided to a "start tools"
        action.

        Arguments:

            data: a dictionary of the arguments sent to the Tool Meister

        Returns 0 on success, # of failures otherwise.
        """

        if self.state in ("running", "startup"):
            # The "send tool data" action is only allowed when the Tool
            # Meister has left the startup state (received the first "init" at
            # least, and is not running any tools. It is a no-op if a "send"
            # is issued "send" before any tools were started.
            msg = f"send action received in state '{self.state}'"
            self._send_client_status(msg)
            return 1

        if len(set(self._usable_tools.keys()) - set(self.persistent_tool_names)) == 0:
            # We only have persistent tools, nothing to send.
            self._send_client_status("success")
            return 0

        directory = data["directory"]
        try:
            tool_dir = self.directories[directory]
        except KeyError:
            self.logger.error(
                "INTERNAL ERROR - send tools action encountered for a"
                " directory, '%s', that is different from any previous"
                " start tools directory, %r",
                directory,
                self.directories.keys(),
            )
            self._send_client_status("internal-error")
            return 1

        if self._params.hostname == self._params.controller:
            del self.directories[directory]
            self.logger.info(
                "%s: send_tools (no-op) %s %s",
                self._params.hostname,
                self._params.group,
                tool_dir,
            )
            # Note that we don't have a directory to send when a Tool
            # Meister runs on the same host as the controller.
            self._send_client_status("success")
            return 0

        if self._params.label:
            assert tool_dir.name == f"{self._params.label}:{self._params.hostname}", (
                f"Logic Bomb! Final path component of the tool directory is"
                f" '{tool_dir.name}', not our label and host name"
                f" '{self._params.label}:{self._params.hostname}'"
            )
        else:
            assert tool_dir.name == self._params.hostname, (
                f"Logic Bomb! Final path component of the tool directory is"
                f" '{tool_dir.name}', not our host name '{self._params.hostname}'"
            )

        directory_bytes = data["directory"].encode("utf-8")
        tool_data_ctx = hashlib.md5(directory_bytes).hexdigest()
        failures = self._send_directory(tool_dir, "tool-data", tool_data_ctx)

        if failures == 0:
            del self.directories[directory]

        self._send_client_status(
            "success" if failures == 0 else f"{failures} failures sending tool data"
        )
        return failures

    def end_tools(self, data: Dict[str, str]) -> int:
        """Stop all the persistent data collection tools.

        Arguments:

            data: a dictionary of the arguments sent to the Tool Meister

        Returns 0 on success, # of failures otherwise.
        """
        failures = 0
        tool_cnt = 0
        for name, persistent_tool in self._persistent_tools.items():
            assert name in self._usable_tools, (
                f"Logic bomb!  Persistent tool, '{name}' not in registered"
                f" list of tools, '{self._usable_tools!r}'."
            )
            tool_cnt += 1
            try:
                persistent_tool.stop()
            except Exception:
                self.logger.exception(
                    "Failed to stop persistent tool %s running in background", name
                )
                failures += 1
        for name, persistent_tool in self._persistent_tools.items():
            tool_cnt += 1
            try:
                persistent_tool.wait()
            except Exception:
                self.logger.exception(
                    "Failed to wait for persistent tool %s to stop running"
                    " in background",
                    name,
                )
                failures += 1

        # Remove persistent tool temporary working directory
        directory = data["directory"]
        tool_dir = self.directories[directory]

        self.logger.debug(
            "%s: deleting persistent tool tmp directory %s %s",
            self._params.hostname,
            self._params.group,
            tool_dir,
        )
        unexpected_files = []
        for dir, _, files in os.walk(tool_dir):
            dirpath = Path(dir).relative_to(tool_dir)
            if files:
                unexpected_files += map(lambda x: f"{dirpath}/{x}", files)

        if unexpected_files:
            self.logger.warning(
                "%s: unexpected temp files %s",
                self._params.hostname,
                ",".join(sorted(unexpected_files)),
            )
        try:
            shutil.rmtree(tool_dir)
        except Exception:
            self.logger.exception(
                "Failed to remove persistent tool data tmp directory: %s", tool_dir
            )
        del self.directories[directory]
        if failures > 0:
            msg = f"{failures} of {tool_cnt} failed stopping persistent tools"
            self._send_client_status(msg)
        else:
            self._send_client_status("success")
        return failures

    def sysinfo(self, data: Dict[str, str]) -> int:
        """sysinfo - collect all the sysinfo data for this host.

        Arguments:

            data: a dictionary of the arguments sent to the Tool Meister

        Returns 0 on success, # of failures otherwise.
        """
        if self.state in ("running", "idle"):
            # The "gather system information" action is only allowed when the
            # Tool Meister first starts ("startup"), and when it is ready for
            # shutting down ("shutdown").
            msg = f"sysinfo action received in state '{self.state}'"
            self._send_client_status(msg)
            return 1

        sysinfo_args = data["args"]
        self.logger.debug("sysinfo args: %r", sysinfo_args)
        if not sysinfo_args:
            sysinfo_args = "none"

        if self._params.label:
            sub_dir = f"{self._params.label}:{self._params.hostname}"
        else:
            sub_dir = self._params.hostname

        if self._params.hostname == self._params.controller:
            try:
                sysinfo_dir = Path(data["directory"]).resolve(strict=True)
            except Exception:
                self.logger.exception(
                    "Failed to access provided sysinfo directory, %s", data["directory"]
                )
                self._send_client_status("internal-error")
                return 1
        else:
            try:
                sysinfo_dir = Path(
                    tempfile.mkdtemp(
                        dir=self._tmp_dir,
                        prefix=f"tm.{self._params.group}.{os.getpid()}.",
                    )
                ).resolve(strict=True)
            except Exception:
                self.logger.exception(
                    "Failed to create temporary directory for sysinfo operation"
                )
                self._send_client_status("internal-error")
                return 1

        instance_dir = sysinfo_dir / sub_dir
        try:
            instance_dir.mkdir()
        except Exception:
            self.logger.exception(
                "Failed to create instance directory for sysinfo operation"
            )
            self._send_client_status("internal-error")
            return 1

        command = [self.sysinfo_dump, str(instance_dir), sysinfo_args, "parallel"]

        self.logger.info("pbench-sysinfo-dump -- %s", " ".join(command))

        failures = 0
        msg = ""
        o_file = instance_dir / "tm-sysinfo.out"
        e_file = instance_dir / "tm-sysinfo.err"
        try:
            with o_file.open("w") as ofp, e_file.open("w") as efp:
                my_env = os.environ.copy()
                my_env["sysinfo_install_dir"] = self.pbench_install_dir
                my_env["sysinfo_full_hostname"] = self._params.hostname
                cp = subprocess.run(
                    command,
                    cwd=instance_dir,
                    stdin=None,
                    stdout=ofp,
                    stderr=efp,
                    env=my_env,
                )
        except Exception as exc:
            msg = f"Failed to collect system information: {exc}"
            self.logger.exception(msg)
            failures += 1
        else:
            if cp.returncode != 0:
                msg = f"failed to collect system information; return code: {cp.returncode}"
                self.logger.error(msg)
                failures += 1

        if self._params.hostname == self._params.controller:
            self.logger.info(
                "%s: sysinfo send (no-op) %s %s",
                self._params.hostname,
                self._params.group,
                instance_dir,
            )
        else:
            directory_bytes = data["directory"].encode("utf-8")
            sysinfo_data_ctx = hashlib.md5(directory_bytes).hexdigest()
            failures = self._send_directory(
                instance_dir, "sysinfo-data", sysinfo_data_ctx
            )

        self._send_client_status(
            "success"
            if failures == 0
            else f"{failures} failures sending sysinfo data"
            if not msg
            else msg
        )

        return failures


def get_logger(PROG: str, daemon: bool = False, level: str = "info") -> logging.Logger:
    """Contruct a logger for a Tool Meister instance.

    If in the Unit Test environment, just log to console.
    If in non-unit test environment:
       If daemonized, log to syslog and log back to Redis.
       If not daemonized, log to console AND log back to Redis
    """
    logger = logging.getLogger(PROG)
    if level == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logger.setLevel(log_level)

    unit_tests = bool(os.environ.get("_PBENCH_UNIT_TESTS"))
    if unit_tests or not daemon:
        sh = logging.StreamHandler()
    else:
        sh = logging.handlers.SysLogHandler()
    sh.setLevel(log_level)
    shf = logging.Formatter(fmtstr_ut if unit_tests else fmtstr)
    sh.setFormatter(shf)
    logger.addHandler(sh)

    return logger


class Arguments(NamedTuple):
    host: str
    port: int
    key: str
    daemonize: bool
    level: str


def driver(
    PROG: str,
    tar_path: str,
    sysinfo_dump: str,
    pbench_install_dir: Path,
    tmp_dir: Path,
    parsed: Arguments,
    params: Dict[str, Any],
    redis_server: redis.Redis,
    logger: logging.Logger = None,
):
    """Create and drive a Tool Meister instance"""
    if logger is None:
        logger = get_logger(PROG, level=parsed.level)

    # Add a logging handler to send logs back to the Redis server, with each
    # log entry prepended with the given hostname parameter.
    channel_prefix = params["channel_prefix"]
    rh = RedisHandler(
        channel=f"{channel_prefix}-{tm_channel_suffix_to_logging}",
        hostname=params["hostname"],
        redis_client=redis_server,
    )
    redis_fmtstr = fmtstr_ut if os.environ.get("_PBENCH_UNIT_TESTS") else fmtstr
    rhf = logging.Formatter(redis_fmtstr)
    rh.setFormatter(rhf)
    logger.addHandler(rh)

    logger.debug("params_key (%s): %r", parsed.key, params)

    # FIXME: we should establish signal handlers that do the following:
    #   a. handle graceful termination (TERM, INT, QUIT)
    #   b. log operational state (HUP maybe?)

    ret_val = 0
    try:
        with ToolMeister(
            pbench_install_dir,
            tmp_dir,
            tar_path,
            sysinfo_dump,
            params,
            redis_server,
            logger,
        ) as tm:
            logger.debug("waiting ...")
            for action, data in tm.wait_for_command():
                logger.debug("acting ... %s, %r", action.__name__, data)
                failures = action(data)
                if failures > 0:
                    logger.warning(
                        "%d failures encountered for action, %r," " on data, %r",
                        failures,
                        action,
                        data,
                    )
                logger.debug("waiting ...")
    except Exception:
        logger.exception("Unexpected error encountered")
        ret_val = 10
    finally:
        if rh.errors > 0 or rh.redis_errors > 0 or rh.dropped > 0:
            logger.warning(
                "RedisHandler redis_errors: %d, errors: %d, dropped: %d",
                rh.errors,
                rh.redis_errors,
                rh.dropped,
            )
    return ret_val


def daemon(
    PROG: str,
    tar_path: str,
    sysinfo_dump: str,
    pbench_install_dir: Path,
    tmp_dir: Path,
    parsed: Arguments,
    params: Dict[str, Any],
    redis_server: redis.Redis,
):
    """Daemonize a Tool Meister instance"""
    # Disconnect any Redis server object connection pools to avoid problems
    # when we daemonize.
    redis_server.connection_pool.disconnect()
    del redis_server

    # Before we daemonize, flush any data written to stdout or stderr.
    sys.stderr.flush()
    sys.stdout.flush()

    if params["hostname"] != params["controller"]:
        working_dir = tmp_dir
    else:
        working_dir = Path(".")
    pidfile_name = working_dir / "tm.pid"
    d_out = working_dir / "tm.out"
    d_err = working_dir / "tm.err"
    pfctx = pidfile.PIDFile(pidfile_name)
    with d_out.open("w") as sofp, d_err.open("w") as sefp, DaemonContext(
        stdout=sofp,
        stderr=sefp,
        working_directory=working_dir,
        umask=0o022,
        pidfile=pfctx,
    ):
        # We need a logger earlier than the driver now that we are daemonized.
        logger = get_logger(PROG, daemon=True, level=parsed.level)

        # Previously we validated the Tool Meister parameters, and in doing so
        # made sure we had proper access to the Redis server.
        #
        # We can safely re-create the ToolMeister object now that we are
        # "daemonized".
        logger.debug("re-constructing Redis server object")
        try:
            # NOTE: we have to recreate the connection to the redis service
            # since all open file descriptors were closed as part of the
            # daemonizing process.
            redis_server = redis.Redis(host=parsed.host, port=parsed.port, db=0)
        except Exception as exc:
            logger.error(
                "Unable to construct Redis server object, %s:%s: %s",
                parsed.host,
                parsed.port,
                exc,
            )
            return 8
        else:
            logger.debug("re-constructed Redis server object")
        return driver(
            PROG,
            tar_path,
            sysinfo_dump,
            pbench_install_dir,
            tmp_dir,
            parsed,
            params,
            redis_server,
            logger=logger,
        )


def start(prog: Path, parsed: Arguments) -> int:
    """
    Start a Tool Meister instance; including logging setup, initial connection
    to Redis(), fetching and validating operational paramters from Redis(), and
    daemonization of the ToolMeister.

    Args:
        prog    The Path to the program binary
        parsed  The Namespace resulting from parse_args

    Returns:
        integer status code (0 success, > 0 coded failure)
    """
    PROG = prog.name

    tar_path = shutil.which("tar")
    if tar_path is None:
        print(f"{PROG}: External 'tar' executable not found.", file=sys.stderr)
        return 2

    # The Tool Meister executable is in:
    #   ${pbench_install_dir}/util-scripts/tool-meister/pbench-tool-meister
    # So .parent at each level is:
    #   prog       ${pbench_install_dir}/util-scripts/tool-meister/pbench-tool-meister
    #     .parent   ${pbench_install_dir}/util-scripts/tool-meister
    #     .parent   ${pbench_install_dir}/util-scripts
    #     .parent   ${pbench_install_dir}
    pbench_install_dir = prog.parent.parent.parent

    # The pbench-sysinfo-dump utility is no longer in the path where the CLI
    # executables are found.  So we have to add to the default PATH to be sure
    # it can be found, but only if it is not already present.
    _path = os.environ.get("PATH", "")
    _path_list = _path.split(os.pathsep)
    for _path_el in _path_list:
        if _path_el.endswith("tool-meister"):
            break
    else:
        _path_list.append(str(prog.parent))
        os.environ["PATH"] = os.pathsep.join(_path_list)

    sysinfo_dump = shutil.which("pbench-sysinfo-dump")
    if sysinfo_dump is None:
        print(
            f"{PROG}: External 'pbench-sysinfo-dump' executable not found.",
            file=sys.stderr,
        )
        return 3

    tmp_dir_str = os.environ.get("pbench_tmp", "/var/tmp")
    try:
        # The temporary directory to use for capturing all tool data.
        tmp_dir = Path(tmp_dir_str).resolve(strict=True)
    except Exception as e:
        print(
            f"{PROG}: Error working with temporary directory, '{tmp_dir_str}': {e}",
            file=sys.stderr,
        )
        return 4
    else:
        if not tmp_dir.is_dir():
            print(
                f"{PROG}: The temporary directory, '{tmp_dir_str}', does not resolve to a directory",
                file=sys.stderr,
            )
            return 4

    try:
        redis_server = redis.Redis(host=parsed.host, port=parsed.port, db=0)
    except Exception as exc:
        print(
            f"{PROG}: Unable to construct Redis client, {parsed.host}:{parsed.port}: {exc}",
            file=sys.stderr,
        )
        return 5

    try:
        # Wait for the key to show up with a value.
        params_str = wait_for_conn_and_key(redis_server, parsed.key, PROG)
        params = json.loads(params_str)
        # Validate the Tool Meister parameters without constructing an object
        # just yet, as we want to make sure we can talk to the redis server
        # before we go through the trouble of daemonizing below.
        ToolMeister.fetch_params(params)
    except Exception as exc:
        print(
            f"{PROG}: Unable to fetch and decode parameter key, '{parsed.key}': {exc}",
            file=sys.stderr,
        )
        return 6

    func = daemon if parsed.daemonize else driver
    func(
        PROG,
        tar_path,
        sysinfo_dump,
        pbench_install_dir,
        tmp_dir,
        parsed,
        params,
        redis_server,
    )


def main(argv: List[str]):
    """Main program for the Tool Meister.

    Arguments:  argv - a list of parameters

                argv[1] - host name or IP address of Redis Server
                argv[2] - port number of Redis Server
                argv[3] - name of key in Redis Server for operational
                          parameters
                argv[4] - "yes" to run as a daemon
                argv[5] - desired debug level

    Returns 0 on success, > 0 when an error occurs.
    """
    prog = Path(argv[0])
    PROG = prog.name
    try:
        parsed = Arguments(
            host=argv[1],
            port=int(argv[2]),
            key=argv[3],
            daemonize=argv[4] == "yes" if len(argv) > 4 else False,
            level=argv[5] if len(argv) > 5 else "info",
        )
    except (ValueError, IndexError) as e:
        print(f"{PROG}: Invalid arguments, {argv!r}: {e}", file=sys.stderr)
        return 1
    else:
        if not parsed.host or not parsed.port or not parsed.key:
            print(
                f"{PROG}: Invalid arguments, {argv!r}: must not be blank",
                file=sys.stderr,
            )
            return 1

    return start(prog, parsed)
