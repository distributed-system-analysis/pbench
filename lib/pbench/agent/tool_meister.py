#!/usr/bin/env python3
# -*- mode: python -*-

"""pbench-tool-meister

Handles the life-cycle executing a given tool on a host. The tool meister
performs the following operations:

  1. Ensures the given tool exists with the supported version
  2. Fetches the parameters configured for the tool
  3. Waits for the message to start the tool
     a. Messages contain three pieces of information:
        the next operational state to move to, the tool group being for which
        the operation will be applied, and the directory in which the tool-
        data-sink will collect and store all the tool data during send
        operations
  4. Waits for the message to stop the tool
  5. Waits for the message to send the tool data remotely
  6. Repeats steps 3 - 5 until a "terminate" message is received

If a SIGTERM or SIGQUIT signal is sent to the tool meister, any existing
running tool is shutdown, all local data is removed, and the tool meister
exits.

A redis [1] instance is used as the communication mechanism between the
various tool meisters on nodes and the benchmark driver. The redis instance is
used both to communicate the initial data set describing the tools to use, and
their parameteres, for each tool meister, as well as a pub/sub for
coordinating starts and stops of all the tools.

The tool meister is given two arguments when started: the redis server to use,
and the redis key to fetch its configuration from for its operation.

[1] https://redis.io/
"""

import errno
import hashlib
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
import time

from distutils.spawn import find_executable
from pathlib import Path

import pidfile
import redis

from daemon import DaemonContext

from pbench.common.utils import md5sum
from pbench.agent.constants import (
    tm_allowed_actions,
    tm_channel_suffix_to_tms,
    tm_channel_suffix_from_tms,
    tm_channel_suffix_to_logging,
    TDS_RETRY_PERIOD_SECS,
)
from pbench.agent.redis import RedisHandler, RedisChannelSubscriber
from pbench.agent.toolmetadata import ToolMetadata
from pbench.agent.utils import collect_local_info


# Logging format string for unit tests
fmtstr_ut = "%(levelname)s %(name)s %(funcName)s -- %(message)s"
fmtstr = "%(asctime)s %(levelname)s %(process)s %(thread)s %(name)s %(funcName)s %(lineno)d -- %(message)s"


class ToolException(Exception):
    """ToolException - Exception class for all exceptions raised by the Tool
    class object methods.
    """

    pass


class Tool:
    """Encapsulates all the state needed to manage a tool running as a background
    process.

    The ToolMeister class uses one Tool object per running tool.

    FIXME: this class effectively re-implements the former
    "tool-scripts/base-tool" bash script.
    """

    _tool_type = "Transient"

    def __init__(
        self, name, tool_opts, pbench_install_dir=None, tool_dir=None, logger=None,
    ):
        assert logger is not None, "Logic bomb!  no logger provided!"
        self.logger = logger
        self.name = name
        self.tool_opts = tool_opts
        assert (
            pbench_install_dir is not None
        ), "Logic bomb!  no installation directory provided!"
        self.pbench_install_dir = pbench_install_dir
        self.tool_dir = tool_dir
        self.start_process = None
        self.stop_process = None

    def _check_no_processes(self):
        if self.start_process is not None:
            raise ToolException(
                f"Tool({self.name}) has an unexpected start process running"
            )
        if self.stop_process is not None:
            raise ToolException(
                f"Tool({self.name}) has an unexpected stop process running"
            )

    def install(self):
        """Synchronously runs the tool --install mode capturing the return code and
        output, returning them as a tuple to the caller.
        """
        args = [
            f"{self.pbench_install_dir}/tool-scripts/{self.name}",
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
        return (cp.returncode, cp.stdout.strip())

    def start(self):
        """Creates the background process running the tool's "start" operation.
        """
        assert self.tool_dir is not None, "Logic bomb!  no tool directory provided!"
        self._check_no_processes()
        args = [
            f"{self.pbench_install_dir}/tool-scripts/{self.name}",
            "--start",
            f"--dir={self.tool_dir}",
            self.tool_opts,
        ]
        self.logger.info("%s: start_tool -- %s", self.name, " ".join(args))
        o_file = self.tool_dir / f"tm-{self.name}-start.out"
        e_file = self.tool_dir / f"tm-{self.name}-start.err"
        with o_file.open("w") as ofp, e_file.open("w") as efp:
            self.start_process = subprocess.Popen(
                args,
                cwd=self.tool_dir,
                stdin=subprocess.DEVNULL,
                stdout=ofp,
                stderr=efp,
            )

    def stop(self):
        """Stops the background process by running the tool's "stop" operation.
        """
        assert self.tool_dir is not None, "Logic bomb!  no tool directory provided!"
        if self.start_process is None:
            raise ToolException(f"Tool({self.name})'s start process not running")
        if self.stop_process is not None:
            raise ToolException(
                f"Tool({self.name}) has an unexpected stop process running"
            )

        # Before we "stop" a tool, check to see if a "{tool}/{tool}.pid" file
        # exists.  If it doesn't, wait for a second for it to show up.  If
        # after a second it does not show up, then give up waiting and just call
        # the stop method.
        tool_pid_file = self.tool_dir / self.name / f"{self.name}.pid"
        cnt = 0
        while not tool_pid_file.exists() and cnt < 100:
            time.sleep(0.1)
            cnt += 1
        if not tool_pid_file.exists():
            self.logger.warning(
                "Tool(%s) pid file, %s, does not exist after waiting 10 seconds",
                self.name,
                tool_pid_file,
            )

        args = [
            f"{self.pbench_install_dir}/tool-scripts/{self.name}",
            "--stop",
            f"--dir={self.tool_dir}",
            self.tool_opts,
        ]
        self.logger.info("%s: stop_tool -- %s", self.name, " ".join(args))
        o_file = self.tool_dir / f"tm-{self.name}-stop.out"
        e_file = self.tool_dir / f"tm-{self.name}-stop.err"
        with o_file.open("w") as ofp, e_file.open("w") as efp:
            self.stop_process = subprocess.Popen(
                args,
                cwd=self.tool_dir,
                stdin=subprocess.DEVNULL,
                stdout=ofp,
                stderr=efp,
            )

    def _wait_for_process(self, process):
        """_wait_for_process - generic method to wait for a given process to
        stop after 30 seconds, emitting a message every 5 seconds in between.

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
                    self.logger.info(
                        "%s tool %s has not stopped after %d seconds",
                        self._tool_type,
                        self.name,
                        5 * (6 - count),
                    )
        return sts

    def wait(self):
        """Wait for any tool processes to terminate after a "stop" process has
        completed.

        Waits for the tool's "stop" process to complete, if started, then
        waits for the tool's start process to complete.
        """
        if self.stop_process is None:
            raise ToolException(f"Tool({self.name}) wait not called after 'stop'")
        if self.start_process is None:
            raise ToolException(
                f"Tool({self.name}) does not have a start process running"
            )

        self.logger.info("Waiting for transient tool %s stop process", self.name)
        # We wait for the stop process to finish first ...
        sts = self._wait_for_process(self.stop_process)
        if sts is None:
            # The stop process did not terminate gracefully after 30 seconds,
            # so we bring out the big guns ...
            self.stop_process.kill()
            self.logger.error(
                "Killed un-responsive transient tool %s stop process after"
                " 30 seconds",
                self.name,
            )
        elif sts != 0 and sts != -(signal.SIGTERM):
            self.logger.warning(
                "Transient tool %s stop process failed with %d", self.name, sts
            )
        self.stop_process = None

        # ... then we wait for the start process to finish, but we only wait
        # for 30 seconds before we kill it.
        self.logger.info("Waiting for transient tool %s start process", self.name)
        try:
            sts = self.start_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.start_process.kill()
            self.logger.warning(
                "Killed un-responsive transient tool %s start process after"
                " 30 seconds",
                self.name,
            )
        else:
            if sts != 0 and sts != -(signal.SIGTERM):
                self.logger.warning(
                    "Transient tool %s start process failed with %d", self.name, sts
                )
        self.start_process = None


class PersistentTool(Tool):
    """PersistentTool - Encapsulates all the states needed to run persistent
    tooling in the background.  A PersistentTool extends the base Tool class
    with some simple modifications for stopping the tool without the need for
    an external stop script.

    Each persistent tool extends this intermediate "base" class with its
    own particular behaviors.
    """

    _tool_type = "Persistent"

    def __init__(self, name, tool_opts, logger=None, **kwargs):
        super().__init__(name, tool_opts, logger=logger, **kwargs)
        self.args = None
        self.process = None

    def start(self, env=None):
        assert self.args is not None, "Logic bomb!  {self.name} install had failed!"
        assert (
            self.tool_dir is not None
        ), "Logic bomb!  No persistent tool directory provided!"
        self.tool_dir = self.tool_dir / self.name
        self.tool_dir.mkdir()
        o_file = self.tool_dir / f"tm-{self.name}-start.out"
        e_file = self.tool_dir / f"tm-{self.name}-start.err"
        with o_file.open("w") as ofp, e_file.open("w") as efp:
            if env:
                pp = env["PYTHONPATH"]
                self.logger.debug(
                    "Starting persistent tool %s, env PYTHONPATH=%s, args %r",
                    self.name,
                    pp,
                    self.args,
                )
                self.process = subprocess.Popen(
                    " ".join(self.args),
                    cwd=self.tool_dir,
                    stdout=ofp,
                    stderr=efp,
                    env=self.env,
                    shell=True,
                )
            else:
                self.logger.debug(
                    "Starting persistent tool %s, args %r", self.name, self.args
                )
                self.process = subprocess.Popen(
                    self.args, cwd=self.tool_dir, stdout=ofp, stderr=efp,
                )
        if env:
            pp = env["PYTHONPATH"]
            self.logger.info(
                "Started persistent tool %s, env PYTHONPATH=%s, args %r",
                self.name,
                pp,
                self.args,
            )
        else:
            self.logger.info("Started persistent tool %s, %r", self.name, self.args)

    def stop(self):
        """stop - terminate the persistent tool sub-process.

        This method does not wait for the process to actually exit. The caller
        should issue a wait() for that.
        """
        if self.process is None:
            self.logger.error("Nothing to terminate")
            return

        # First try to gracefully terminate.
        self.process.terminate()
        self.logger.info("Terminate issued for persistent tool %s", self.name)

    def wait(self):
        """wait - Wait for the persistent tool to exit.

        Requires the caller to issue a stop() first.

        The wait() method will wait for 30 seconds before forcibly killing
        the persistent tool sub-process.  It will emit an informational log
        message every 5 seconds in between.
        """
        if self.process is None:
            self.logger.error("Nothing to terminate")
            return

        sts = self._wait_for_process(self.process)
        if sts is None:
            self.process.kill()
            self.logger.error(
                "Killed un-responsive persistent tool %s after 30 seconds", self.name
            )
        elif sts != 0 and sts != -(signal.SIGTERM):
            o_file = self.tool_dir / f"tm-{self.name}-start.out"
            e_file = self.tool_dir / f"tm-{self.name}-start.err"
            stdout = o_file.read_text()
            stderr = e_file.read_text()
            self.logger.warning(
                "Persistent tool %s failed to return success, %d, stdout %r, stderr %r",
                self.name,
                self.process.returncode,
                stdout,
                stderr,
            )
        else:
            self.logger.info("Stopped persistent tool %s", self.name)
        self.process = None


class DcgmTool(PersistentTool):
    """DcgmTool - provide specific persistent tool behaviors for the "dcgm"
    tool.

    In particular, the dcgm tool requires the "--inst" option, requires the
    PYTHONPATH environment variable be set properly, and must use a python2
    environment.
    """

    def __init__(self, name, tool_opts, logger=None, **kwargs):
        super().__init__(name, tool_opts, logger=logger, **kwargs)
        # Looking for required "--inst" option, reformatting appropriately if
        # found.
        tool_opts_l = self.tool_opts.split(" ")
        for opt in tool_opts_l:
            if opt.startswith("--inst="):
                if opt[-1] == "\n":
                    install_path = opt[7:-1]
                else:
                    install_path = opt[7:]
                self.install_path = Path(install_path)
                self.logger.debug(
                    "install path for tool %s, %s", name, self.install_path
                )
                break
        else:
            self.install_path = None
            self.logger.debug("missing install path")
        if self.install_path is None:
            self.script_path = None
            self.args = None
            self.env = None
        else:
            self.script_path = (
                self.install_path / "samples" / "scripts" / "dcgm_prometheus.py"
            )
            if not self.script_path.exists():
                self.logger.error("missing script path, %s", self.script_path)
                self.args = None
                self.env = None
            else:
                self.args = ["python2", f"{self.script_path}"]
                new_path_l = [
                    str(self.install_path / "bindings"),
                    str(self.install_path / "bindings" / "common"),
                ]
                unit_tests = bool(os.environ.get("_PBENCH_UNIT_TESTS"))
                prev_path = os.environ.get("PYTHONPATH", "")
                if prev_path and not unit_tests:
                    new_path_l.append(prev_path)
                self.env = os.environ.copy()
                self.env["PYTHONPATH"] = ":".join(new_path_l)

    def install(self):
        if self.install_path is None:
            return (1, "dcgm tool --inst argument missing")
        elif self.args is None:
            return (1, f"dcgm tool path, '{self.script_path}', not found")
        return (0, "dcgm tool properly installed")

    def start(self):
        # The dcgm tool needs PYTHONPATH, and run via the shell.
        super().start(env=self.env)


class NodeExporterTool(PersistentTool):
    """NodeExporterTool - provide specifics for running the "node-exporter"
    tool.

    The only particular behavior is that we find the proper "node_exporter"
    executable in our PATH.
    """

    def __init__(self, name, tool_opts, logger=None, **kwargs):
        super().__init__(name, tool_opts, logger=logger, **kwargs)
        executable = find_executable("node_exporter")
        if executable is None:
            self.args = None
        else:
            self.args = [executable]

    def install(self):
        if self.args is None:
            return (1, "node_exporter tool not found")
        return (0, "node_exporter tool properly installed")


class PcpTool(PersistentTool):
    """PcpTool - provide specifics for running the "pcp" tool, which is really the "pmcd" process.
    """

    # Default path to the "pmcd" executable.
    _pmcd_path_def = "/usr/libexec/pcp/bin/pmcd"

    def __init__(self, name, tool_opts, logger=None, **kwargs):
        super().__init__(name, tool_opts, logger=logger, **kwargs)
        pmcd_path = find_executable("pmcd")
        if pmcd_path is None:
            pmcd_path = self._pmcd_path_def
        executable = os.access(pmcd_path, os.X_OK)
        if executable:
            # FIXME - The Tool Data Sink and Tool Meister have to agree on the
            # exact port number to use.  We can't use the default `pmcd` port
            # number because it might conflict with an existing `pmcd`
            # deployment out of our control.
            self.args = [
                pmcd_path,
                "--foreground",
                "--socket=./pmcd.socket",
                "--port=55677",
                f"--config={self.pbench_install_dir}/templates/pmcd.conf",
            ]
        else:
            self.args = None

    def install(self):
        if self.args is None:
            return (1, "pcp tool (pmcd) not found")
        return (0, "pcp tool (pmcd) properly installed")


class Terminate(Exception):
    """Simple exception to be raised when the Tool Meister main loop should exit
    gracefully.
    """

    pass


class ToolMeisterError(Exception):
    """Simple exception for any errors from the ToolMeister class."""

    pass


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
            "controller": "<hostname of the controller driving all the tool"
                          " meisters; if this tool meister is running locally"
                          " with the controller, then it does not need to send"
                          " data to the tool data sink since it can access the"
                          " ${benchmark_run_dir} and ${benchmark_results_dir}"
                          " directories directly.>",
            "group":      "<Name of the tool group from which the following"
                          " tools data was pulled, passed as the"
                          " --group argument to the individual tools>",
            "hostname":   "<hostname of tool meister, should be same as"
                          " 'hostname -f' where tool meister is running>",
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
            "action":     "<'start'|'stop'|'send'>",
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
    def fetch_params(params):
        """Static help method that allows the method constructing a ToolMeister
        instance to verify the parameters before we actually construct the
        object.

        The definition of the contents of a parameter block is really
        independent of a ToolMeister implementation, but we keep this method
        in the ToolMeister class since it is closely related to the
        implementation.
        """
        try:
            benchmark_run_dir = params["benchmark_run_dir"]
            channel_prefix = params["channel_prefix"]
            controller = params["controller"]
            group = params["group"]
            hostname = params["hostname"]
            tool_metadata = ToolMetadata.tool_md_from_dict(params["tool_metadata"])
            tools = params["tools"]
            label = params["label"]
        except KeyError as exc:
            raise ToolMeisterError(f"Invalid parameter block, missing key {exc}")
        else:
            return (
                benchmark_run_dir,
                channel_prefix,
                controller,
                group,
                hostname,
                tool_metadata,
                tools,
                label,
            )

    _valid_states = frozenset(["startup", "idle", "running", "shutdown"])
    _message_keys = frozenset(["action", "args", "directory", "group"])
    # Most tools we have today are "transient" tools, and are handled by external
    # scripts.  Our two persistent tools are handled in the code directly.
    #
    # FIXME - we should eventually allow them to be loaded externally.
    _tool_name_class_mappings = {
        "dcgm": DcgmTool,
        "node-exporter": NodeExporterTool,
        "pcp": PcpTool,
    }

    def __init__(
        self,
        pbench_install_dir,
        tmp_dir,
        tar_path,
        sysinfo_dump,
        params,
        redis_server,
        logger,
    ):
        """Constructor for the ToolMeister object - sets up the internal state
        given the constructor parameters, setting up the state transition
        table, and forming the various channel names from the channel prefix
        in the params object.
        """
        self.pbench_install_dir = pbench_install_dir
        self._tmp_dir = tmp_dir
        self.tar_path = tar_path
        self.sysinfo_dump = sysinfo_dump
        ret_val = self.fetch_params(params)
        (
            self._benchmark_run_dir,
            self._channel_prefix,
            self._controller,
            self._group,
            self._hostname,
            self._tool_metadata,
            self._tools,
            self._label,
        ) = ret_val
        self._rs = redis_server
        self.logger = logger
        # No running tools at first
        self._running_tools = dict()
        # No persistent tools at first
        self._persistent_tools = dict()
        self.persistent_tool_names = self._tool_metadata.getPersistentTools()
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
        self._to_tms_channel = f"{self._channel_prefix}-{tm_channel_suffix_to_tms}"
        # Name of the channel on which all Tool Meister instances respond.
        self._from_tms_channel = f"{self._channel_prefix}-{tm_channel_suffix_from_tms}"

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
        for name, tool_opts in sorted(self._tools.items()):
            try:
                tklass = self._tool_name_class_mappings[name]
            except KeyError:
                tklass = Tool
            try:
                tool = tklass(
                    name,
                    tool_opts,
                    pbench_install_dir=self.pbench_install_dir,
                    tool_dir=self._tool_dir,
                    logger=self.logger,
                )
                # FIXME - consider running these in parallel.
                tool_installs[name] = tool.install()
            except Exception:
                self.logger.exception("Failed to run tool %s install check", name)
                tool_installs[name] = (-42, "internal-error")
        self._failed_tools = {}
        for name, res in tool_installs.items():
            if res[0] != 0:
                self.logger.debug("Recording failed tool, %s", name)
                self._failed_tools[name] = self._tools[name]
                del self._tools[name]

        started_msg = dict(
            hostname=self._hostname,
            kind="tm",
            label=self._label,
            pid=os.getpid(),
            version=version,
            seqno=seqno,
            sha1=sha1,
            hostname_f=hostdata["f"],
            hostname_s=hostdata["s"],
            hostname_i=hostdata["i"],
            hostname_I=hostdata["I"],
            hostname_A=hostdata["A"],
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
                    "Unable to publish startup ack message, {started_msg!r}"
                )
        self.logger.debug("published %s", self._from_tms_channel)
        return self

    def __exit__(self, *args):
        """Exit context manager method - close down the "to-tms" Redis channel,
        and send the final terminated status to the Tool Data Sink.
        """
        self.logger.info("%s: terminating", self._hostname)
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
            elif tmp_data["group"] is not None and tmp_data["group"] != self._group:
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
        self.logger.debug("%s: wait_for_command %s", self._hostname, self.state)
        for action, data in self._gen_data():
            if action == "terminate":
                self.logger.debug("%s: msg - %r", self._hostname, data)
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
            self.logger.debug("%s: msg - %r", self._hostname, data)
            yield action_method, data

    def _send_client_status(self, status):
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
        msg_d = dict(kind="tm", hostname=self._hostname, status=status)
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

    def init_tools(self, data):
        """init_tools - setup all registered tools which have data collectors.

        The Tool Data Sink will be setting up the actual processes which
        collect data from these tools.
        """
        # Name of the temporary tool data directory to use when invoking
        # tools.  This is a local temporary directory when the Tool Meister is
        # remote from the pbench controller.
        if self._controller == self._hostname:
            # This is the case when the Tool Meister instance is running on
            # the same host as the controller.  We just use the directory
            # given to us in the `start` message.
            try:
                _dir = Path(data["directory"]).resolve(strict=True)
            except Exception:
                self.logger.exception(
                    "Failed to access provided result directory, %s", data["directory"]
                )
                self._send_client_status("internal-error")
                return False
        else:
            try:
                _dir = Path(
                    tempfile.mkdtemp(
                        dir=self._tmp_dir, prefix=f"tm.{self._group}.{os.getpid()}."
                    )
                )
            except Exception:
                self.logger.exception(
                    "Failed to create temporary directory for start operation"
                )
                self._send_client_status("internal-error")
                return False
        if self._label:
            sub_dir = f"{self._label}:{self._hostname}"
        else:
            sub_dir = self._hostname
        _tool_dir = _dir / sub_dir
        try:
            _tool_dir.mkdir()
        except Exception:
            self.logger.exception(
                "Failed to create local result directory, %s", _tool_dir
            )
            self._send_client_status("internal-error")
            return False
        failures = 0
        tool_cnt = 0
        for name, tool_opts in sorted(self._tools.items()):
            try:
                tklass = self._tool_name_class_mappings[name]
            except KeyError:
                pass
            else:
                tool_cnt += 1
                try:
                    persistent_tool = tklass(
                        name,
                        tool_opts,
                        pbench_install_dir=self.pbench_install_dir,
                        tool_dir=_tool_dir,
                        logger=self.logger,
                    )
                    persistent_tool.start()
                except Exception:
                    self.logger.exception(
                        "Failed to init PersistentTool %s running in background", name
                    )
                    failures += 1
                else:
                    self._persistent_tools[name] = persistent_tool
                    self.logger.debug("NAME: " + name + "  TOOL OPTS: " + tool_opts)
        if failures > 0:
            msg = f"{failures} of {tool_cnt} persistent tools failed to start"
            self._send_client_status(msg)
        else:
            self._send_client_status("success")
        return failures

    def start_tools(self, data):
        """start_tools - start all registered tools executing in the background

        The 'action' and 'group' values of the payload have already been
        validated before this "start tools" action is invoked.

        If this Tool Meister instance is running on the same host as the
        controller, we'll use the given "directory" argument directly for
        where tools will store their collected data.  When this Tool Meister
        instance is remote, we'll use a temporary directory on that remote
        host.
        """
        if self._running_tools or self._directory is not None:
            self.logger.error(
                "INTERNAL ERROR - encountered previously running tools, %r",
                self._running_tools,
            )
            self._send_client_status("internal-error")
            return False

        # script_path=`dirname $0`
        # script_name=`basename $0`
        # pbench_bin="`cd ${script_path}/..; /bin/pwd`"
        # action=`echo ${script_name#pbench-} | awk -F- '{print $1}'`
        # dir=${1}; shift (-d|--dir)

        # Name of the temporary tool data directory to use when invoking
        # tools.  This is a local temporary directory when the Tool Meister is
        # remote from the pbench controller.
        if self._controller == self._hostname:
            # This is the case when the Tool Meister instance is running on
            # the same host as the controller.  We just use the directory
            # given to us in the `start` message.
            try:
                _dir = Path(data["directory"]).resolve(strict=True)
            except Exception:
                self.logger.exception(
                    "Failed to access provided result directory, %s", data["directory"]
                )
                self._send_client_status("internal-error")
                return False
        else:
            try:
                _dir = Path(
                    tempfile.mkdtemp(
                        dir=self._tmp_dir, prefix=f"tm.{self._group}.{os.getpid()}."
                    )
                )
            except Exception:
                self.logger.exception(
                    "Failed to create temporary directory for start operation"
                )
                self._send_client_status("internal-error")
                return False
        if self._label:
            sub_dir = f"{self._label}:{self._hostname}"
        else:
            sub_dir = self._hostname
        self._tool_dir = _dir / sub_dir
        try:
            self._tool_dir.mkdir()
        except Exception:
            self.logger.exception(
                "Failed to create local result directory, %s", self._tool_dir
            )
            self._send_client_status("internal-error")
            return False
        self._directory = data["directory"]

        # tool_group_dir="$pbench_run/tools-$group"
        # for this_tool_file in `/bin/ls $tool_group_dir`; do
        # 	tool_opts=()
        # 	while read line; do
        # 		tool_opts[$i]="$line"
        # 		((i++))
        # 	done < "$tool_group_dir/$this_tool_file"
        # name="$this_tool_file"
        failures = 0
        tool_cnt = 0
        for name, tool_opts in sorted(self._tools.items()):
            if name in self.persistent_tool_names:
                continue
            tool_cnt += 1
            try:
                tool = Tool(
                    name,
                    tool_opts,
                    pbench_install_dir=self.pbench_install_dir,
                    tool_dir=self._tool_dir,
                    logger=self.logger,
                )
                tool.start()
            except Exception:
                self.logger.exception(
                    "Failed to start tool %s running in background", name
                )
                failures += 1
                continue
            else:
                self._running_tools[name] = tool
        if failures > 0:
            msg = f"{failures} of {tool_cnt} tools failed to start"
            self._send_client_status(msg)
        else:
            self._send_client_status("success")
        return failures

    def _wait_for_tools(self):
        """_wait_for_tools - convenience method to properly wait for all the
        currently running tools to finish before returning to the caller.

        Returns the # of failures encountered waiting for tools, logging any
        errors along the way.
        """
        failures = 0
        for name in sorted(self._tools.keys()):
            try:
                tool = self._running_tools[name]
            except KeyError:
                assert (
                    name in self.persistent_tool_names
                ), f"tool {name} not found in list of persistent tools"
            else:
                try:
                    tool.wait()
                except Exception:
                    self.logger.exception(
                        "Failed to wait for tool %s to stop running in background", name
                    )
                    failures += 1
        return failures

    def stop_tools(self, data):
        """stop_tools - stop any running tools.

        The 'action' and 'group' values of the payload have already been
        validated before this "stop tools" action is invoked.

        This method only proceeds if the 'directory' entry value of the
        payload matches what was previously provided to a "start tools"
        action.
        """
        if self._directory != data["directory"]:
            self.logger.error(
                "INTERNAL ERROR - stop tools action encountered for a"
                " directory, '%s', that is different from the previous"
                " start tools, '%s'",
                data["directory"],
                self._directory,
            )
            return False

        failures = 0
        tool_cnt = 0
        for name in sorted(self._tools.keys()):
            tool_cnt += 1
            try:
                tool = self._running_tools[name]
            except KeyError:
                assert (
                    name in self.persistent_tool_names
                ), f"tool {name} not found in list of persistent tools"
            else:
                try:
                    tool.stop()
                except Exception:
                    self.logger.exception(
                        "Failed to stop tool %s running in background", name
                    )
                    failures += 1
        failures += self._wait_for_tools()

        # Clean up the running tools data structure explicitly ahead of
        # potentially receiving another start tools.
        for name in sorted(self._tools.keys()):
            try:
                del self._running_tools[name]
            except KeyError:
                pass

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

    def _send_directory(self, directory, uri, ctx):
        """_send_directory - tar up the given directory and send via PUT to the
        URL constructed from the "uri" fragment, using the provided context.

        The directory argument is a Path object who last element is a
        directory with a name that is the same as the self._hostname or
        {self._label}:{self._hostname}, referred to as the target_dir.

        The uri and ctx arguments are used to form the final URL as defined by:

           f"http://{self._controller}:8080/{uri}/{ctx}/{target_dir}"

        """
        if self._label:
            assert (
                directory.name == f"{self._label}:{self._hostname}"
            ), f"Expected directory target with <label>:<hostname>, '{directory}'"
        else:
            assert (
                directory.name == self._hostname
            ), f"Expected directory target with <hostname>, '{directory}'"

        failures = 0
        target_dir = directory.name
        parent_dir = directory.parent
        tar_file = parent_dir / f"{target_dir}.tar.xz"
        o_file = parent_dir / f"{target_dir}.tar.out"
        e_file = parent_dir / f"{target_dir}.tar.err"
        try:
            # Invoke tar directly for efficiency.
            with o_file.open("w") as ofp, e_file.open("w") as efp:
                cp = subprocess.run(
                    [
                        self.tar_path,
                        "--create",
                        "--xz",
                        "--force-local",
                        f"--file={tar_file}",
                        target_dir,
                    ],
                    cwd=parent_dir,
                    stdin=None,
                    stdout=ofp,
                    stderr=efp,
                )
        except Exception:
            self.logger.exception("Failed to create tar ball '%s'", tar_file)
            failures += 1
        else:
            try:
                if cp.returncode != 0:
                    self.logger.error(
                        "Failed to create tar ball; return code: %d", cp.returncode,
                    )
                    failures += 1
                else:
                    try:
                        tar_md5 = md5sum(tar_file)
                    except Exception:
                        self.logger.exception("Failed to read tar ball, '%s'", tar_file)
                        failures += 1
                    else:
                        try:
                            o_file.unlink()
                        except Exception as exc:
                            self.logger.warning(
                                "Failure removing tar command output file, %s: %s",
                                o_file,
                                exc,
                            )
                        try:
                            e_file.unlink()
                        except Exception as exc:
                            self.logger.warning(
                                "Failure removing tar command output file, %s: %s",
                                e_file,
                                exc,
                            )

                        self.logger.debug(
                            "%s: starting send_data group=%s, directory=%s",
                            self._hostname,
                            self._group,
                            self._directory,
                        )
                        headers = {"md5sum": tar_md5}
                        url = (
                            f"http://{self._controller}:8080/{uri}"
                            f"/{ctx}/{self._hostname}"
                        )
                        sent = False
                        retries = 200
                        while not sent:
                            try:
                                with tar_file.open("rb") as tar_fp:
                                    response = requests.put(
                                        url, headers=headers, data=tar_fp
                                    )
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
                                            "Failed to remove tool data"
                                            " hierarchy, '%s'",
                                            parent_dir,
                                        )
                                        failures += 1
                        self.logger.info(
                            "%s: PUT %s completed %s %s",
                            self._hostname,
                            uri,
                            self._group,
                            directory,
                        )
            except Exception:
                self.logger.exception("Unexpected error encountered")
                failures += 1
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

    def send_tools(self, data):
        """send_tools - send any collected tool data to the tool data sink.

        The 'action' and 'group' values of the payload have already been
        validated before this "send tools" action is invoked.

        This method only proceeds if the 'directory' entry value of the
        payload matches what was previously provided to a "start tools"
        action.
        """

        if self.state in ("running", "startup"):
            # The "send tool data" action is only allowed when the Tool
            # Meister has left the startup state (received the first "init" at
            # least, and is not running any tools. It is a no-op if a "send"
            # is issued "send" before any tools were started.
            msg = f"send action received in state '{self.state}'"
            self._send_client_status(msg)
            return 1

        if len(set(self._tools.keys()) - set(self.persistent_tool_names)) == 0:
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

        if self._hostname == self._controller:
            del self.directories[directory]
            self.logger.info(
                "%s: send_tools (no-op) %s %s", self._hostname, self._group, tool_dir
            )
            # Note that we don't have a directory to send when a Tool
            # Meister runs on the same host as the controller.
            self._send_client_status("success")
            return 0

        if self._label:
            assert tool_dir.name == f"{self._label}:{self._hostname}", (
                f"Logic Bomb! Final path component of the tool directory is"
                f" '{tool_dir.name}', not our label and host name"
                f" '{self._label}:{self._hostname}'"
            )
        else:
            assert tool_dir.name == self._hostname, (
                f"Logic Bomb! Final path component of the tool directory is"
                f" '{tool_dir.name}', not our host name '{self._hostname}'"
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

    def end_tools(self, data):
        """end_tools - stop all the persistent data collection tools."""
        failures = 0
        tool_cnt = 0
        for name, persistent_tool in self._persistent_tools.items():
            assert name in self._tools, (
                f"Logic bomb!  Persistent tool, '{name}' not in registered"
                f" list of tools, '{self._tools!r}'."
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
        if failures > 0:
            msg = f"{failures} of {tool_cnt} failed stopping persistent tools"
            self._send_client_status(msg)
        else:
            self._send_client_status("success")
        return failures

    def sysinfo(self, data):
        """sysinfo - collect all the sysinfo data for this host."""
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

        if self._label:
            sub_dir = f"{self._label}:{self._hostname}"
        else:
            sub_dir = self._hostname

        if self._hostname == self._controller:
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
                        dir=self._tmp_dir, prefix=f"tm.{self._group}.{os.getpid()}."
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
                my_env["pbench_install_dir"] = self.pbench_install_dir
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

        if self._hostname == self._controller:
            self.logger.info(
                "%s: sysinfo send (no-op) %s %s",
                self._hostname,
                self._group,
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


def get_logger(PROG, daemon=False):
    """get_logger - contruct a logger for a Tool Meister instance.

    If in the Unit Test environment, just log to console.
    If in non-unit test environment:
       If daemonized, log to syslog and log back to Redis.
       If not daemonized, log to console AND log back to Redis
    """
    logger = logging.getLogger(PROG)
    if os.environ.get("_PBENCH_TOOL_MEISTER_LOG_LEVEL") == "debug":
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


def driver(
    PROG,
    tar_path,
    sysinfo_dump,
    pbench_install_dir,
    tmp_dir,
    param_key,
    params,
    redis_server,
    logger=None,
):
    """driver - responsible for creating and driving operation of the Tool
    Meister instance
    """
    if logger is None:
        logger = get_logger(PROG)

    # Add a logging handler to send logs back to the Redis server, with each
    # log entry prepended with the given hostname parameter.
    channel_prefix = params["channel_prefix"]
    rh = RedisHandler(
        channel=f"{channel_prefix}-{tm_channel_suffix_to_logging}",
        hostname=params["hostname"],
        redis_client=redis_server,
    )
    if os.environ.get("_PBENCH_TOOL_MEISTER_LOG_LEVEL") == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    rh.setLevel(log_level)
    redis_fmtstr = fmtstr_ut if os.environ.get("_PBENCH_UNIT_TESTS") else fmtstr
    rhf = logging.Formatter(redis_fmtstr)
    rh.setFormatter(rhf)
    logger.addHandler(rh)

    logger.debug("params_key (%s): %r", param_key, params)

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
    PROG,
    tar_path,
    sysinfo_dump,
    pbench_install_dir,
    tmp_dir,
    param_key,
    params,
    redis_server,
    redis_host,
    redis_port,
):
    """daemon - responsible for properly daemonizing the operation of the Tool
    Meister.
    """
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
    pidfile_name = working_dir / f"{param_key}.pid"
    d_out = working_dir / f"{param_key}.out"
    d_err = working_dir / f"{param_key}.err"
    pfctx = pidfile.PIDFile(pidfile_name)
    with d_out.open("w") as sofp, d_err.open("w") as sefp, DaemonContext(
        stdout=sofp,
        stderr=sefp,
        working_directory=working_dir,
        umask=0o022,
        pidfile=pfctx,
    ):
        # We need a logger earlier than the driver now that we are daemonized.
        logger = get_logger(PROG, daemon=True)

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
            redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)
        except Exception as exc:
            logger.error(
                "Unable to construct to Redis server object, %s:%s: %s",
                redis_host,
                redis_port,
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
            param_key,
            params,
            redis_server,
            logger=logger,
        )


def main(argv):
    """Main program for the Tool Meister.

    This function is the simple driver for the tool meister behaviors,
    handling argument processing, logging setup, initial connection to
    Redis(), fetch and validation of operational paramters from Redis(), and
    then the daemonization of the ToolMeister operation.

    Arguments:  argv - a list of parameters

                argv[1] - host name or IP address of Redis Server
                argv[2] - port number of Redis Server
                argv[3] - name of key in Redis Server for operational
                          parameters
                argv[4] - (optional) if value is "yes", then the Tool Meister
                          should daemonize itself.

    Returns 0 on success, > 0 when an error occurs.
    """
    _prog = Path(argv[0])
    PROG = _prog.name

    try:
        redis_host = argv[1]
        redis_port = argv[2]
        param_key = argv[3]
    except IndexError as e:
        print(f"{PROG}: Invalid arguments: {e}", file=sys.stderr)
        return 1
    try:
        daemonize = argv[4]
    except IndexError:
        daemonize = "no"

    tar_path = find_executable("tar")
    if tar_path is None:
        print(f"{PROG}: External 'tar' executable not found.", file=sys.stderr)
        return 2

    # The Tool Meister executable is in:
    #   ${pbench_install_dir}/util-scripts/tool-meister/pbench-tool-meister
    # So .parent at each level is:
    #   _prog       ${pbench_install_dir}/util-scripts/tool-meister/pbench-tool-meister
    #     .parent   ${pbench_install_dir}/util-scripts/tool-meister
    #     .parent   ${pbench_install_dir}/util-scripts
    #     .parent   ${pbench_install_dir}
    pbench_install_dir = _prog.parent.parent.parent

    # The pbench-sysinfo-dump utility is no longer in the path where the CLI
    # executables are found.  So we have to add to the default PATH to be sure
    # it can be found, but only if it is not already present.
    _path = os.environ.get("PATH", "")
    _path_list = _path.split(":")
    for _path_el in _path_list:
        if _path_el.endswith("tool-meister"):
            break
    else:
        _sep = "" if not _path else ":"
        os.environ["PATH"] = f"{_path}{_sep}{_prog.parent}"

    sysinfo_dump = find_executable("pbench-sysinfo-dump")
    if sysinfo_dump is None:
        print(
            f"{PROG}: External 'pbench-sysinfo-dump' executable not found.",
            file=sys.stderr,
        )
        return 3

    try:
        # The temporary directory to use for capturing all tool data.
        tmp_dir = Path(os.environ["pbench_tmp"]).resolve(strict=True)
    except KeyError:
        print(f"{PROG}: Missing pbench_tmp environment variable", file=sys.stderr)
        return 4
    except Exception as e:
        print(
            f"{PROG}: Error working with pbench_tmp environment variable, '{tmp_dir}': {e}",
            file=sys.stderr,
        )
        return 4
    else:
        if not tmp_dir.is_dir():
            print(
                f"{PROG}: The pbench_tmp environment variable, '{tmp_dir}', does not resolve to a directory",
                file=sys.stderr,
            )
            return 4

    try:
        redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)
    except Exception as exc:
        print(
            f"{PROG}: Unable to construct Redis client, {redis_host}:{redis_port}: {exc}",
            file=sys.stderr,
        )
        return 5

    try:
        params_raw = redis_server.get(param_key)
        if params_raw is None:
            print(
                f'{PROG}: Parameter key, "{param_key}" does not exist.', file=sys.stderr
            )
            return 6
        params_str = params_raw.decode("utf-8")
        params = json.loads(params_str)
        # Validate the tool meister parameters without constructing an object
        # just yet, as we want to make sure we can talk to the redis server
        # before we go through the trouble of daemonizing below.
        ToolMeister.fetch_params(params)
    except Exception as exc:
        print(
            f"{PROG}: Unable to fetch and decode parameter key, '{param_key}': {exc}",
            file=sys.stderr,
        )
        return 7

    if daemonize == "yes":
        ret_val = daemon(
            PROG,
            tar_path,
            sysinfo_dump,
            pbench_install_dir,
            tmp_dir,
            param_key,
            params,
            redis_server,
            redis_host,
            redis_port,
        )
    else:
        ret_val = driver(
            PROG,
            tar_path,
            sysinfo_dump,
            pbench_install_dir,
            tmp_dir,
            param_key,
            params,
            redis_server,
        )
    return ret_val
