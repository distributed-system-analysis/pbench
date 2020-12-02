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
import os
import requests
import requests.exceptions
import shutil
import subprocess
import sys
import tempfile
import time

from distutils.spawn import find_executable
from pathlib import Path

import pidfile
import redis

from daemon import DaemonContext
from redis.connection import SERVER_CLOSED_CONNECTION_ERROR

import pbench.agent.toolmetadata as toolmetadata

from pbench.common.utils import md5sum


# FIXME: The client response channel should be in a shared constants module.
client_channel = "tool-meister-client"

# Logging format string for unit tests
fmtstr_ut = "%(levelname)s %(name)s %(funcName)s -- %(message)s"
fmtstr = "%(asctime)s %(levelname)s %(process)s %(thread)s %(name)s %(funcName)s %(lineno)d -- %(message)s"


class RedisHandler(logging.Handler):
    """Publish messages to a given channel on a Redis server.
    """

    def __init__(
        self,
        channel,
        hostname=None,
        redis_client=None,
        level=logging.NOTSET,
        **redis_kwargs,
    ):
        """Create a new logger for the given channel and redis_client.
        """
        super().__init__(level)
        self.channel = channel
        self.hostname = hostname
        self.redis_client = redis_client or redis.Redis(**redis_kwargs)
        self.counter = 0
        self.errors = 0
        self.redis_errors = 0

    def emit(self, record):
        """Publish record to redis logging channel
        """
        try:
            formatted_record = self.format(record)
            self.redis_client.publish(
                self.channel, f"{self.hostname} {self.counter:04d} {formatted_record}"
            )
        except redis.RedisError:
            self.redis_errors += 1
        except Exception:
            self.errors += 1
        finally:
            self.counter += 1


class ToolException(Exception):
    pass


class PersistentTool:
    """
    Encapsulates all the states needed to run persistent tooling in the background.
    The ToolMeister class uses one PersistentTool object per persistent tool.
    """

    def __init__(self, name, tool_opts, logger):
        self.name = name
        self.tool_opts = tool_opts.split(" ")
        self.logger = logger
        self.install_path = None

        # Looking for required --inst option
        # Reformatting appropriately if found
        for opt in self.tool_opts:
            if opt.startswith("--inst="):
                if opt[len(opt) - 1] == "\n":
                    self.install_path = opt[7 : len(opt) - 1]
                else:
                    self.install_path = opt[7:]
                self.logger.debug("FOUND")
            else:
                self.logger.debug("NOT FOUND SOMEHOW")

        self.process = None
        self.failure = False

    def start(self):
        if self.install_path is None:
            self.failure = True
            self.logger.error(
                "No install path properly given as persistent tool option, see /opt/pbench-agent/nodexporter --help"
            )
            return

        if self.name == "node-exporter":
            self.logger.debug(self.install_path)

            if not os.path.isfile(self.install_path + "/node_exporter"):
                self.logger.info(
                    self.install_path + "/node_exporter" + " does not exist"
                )
                self.failure = True
                return 0

            args = [self.install_path + "/node_exporter"]
            self.process = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            )
        elif self.name == "dcgm":
            os.environ["PYTHONPATH"] = (
                self.install_path
                + "/bindings:"
                + self.install_path
                + "/bindings/common"
            )

            script_path = self.install_path + "/samples/scripts/dcgm_prometheus.py"
            if not os.path.isfile(script_path):
                self.logger.info(script_path + " does not exist")
                self.failure = True
                return 0

            args = [f"python2 {script_path}"]
            self.process = subprocess.Popen(args, shell=True)
        else:
            self.logger.error("Invalid persistent tool name")
            self.failure = True
            return 0

        return 1

    def stop(self):
        if not self.failure:
            self.process.terminate()
            self.process.wait()
            return 1

        self.logger.error("Nothing to terminate")
        return 0


class Tool:
    """Encapsulates all the state needed to manage a tool running as a background
    process.

    The ToolMeister class uses one Tool object per running tool.

    FIXME: this class effectively re-implements the former
    "tool-scripts/base-tool" bash script.
    """

    def __init__(self, name, group, tool_opts, pbench_bin, tool_dir, logger):
        self.logger = logger
        self.name = name
        self.group = group
        self.tool_opts = tool_opts
        self.pbench_bin = pbench_bin
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

    def start(self):
        """Creates the background process running the tool's "start" operation.
        """
        self._check_no_processes()
        args = [
            f"{self.pbench_bin}/tool-scripts/{self.name}",
            "--start",
            f"--dir={self.tool_dir}",
            self.tool_opts,
        ]
        self.logger.info("%s: start_tool -- %s", self.name, " ".join(args))
        o_file = self.tool_dir / f"tm-{self.name}-start.out"
        e_file = self.tool_dir / f"tm-{self.name}-start.err"
        with o_file.open("w") as ofp, e_file.open("w") as efp:
            self.start_process = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=ofp, stderr=efp
            )

    def stop(self):
        """Stops the background process by running the tool's "stop" operation.
        """
        if self.start_process is None:
            raise ToolException(f"Tool({self.name})'s start process not running")
        if self.stop_process is not None:
            raise ToolException(
                f"Tool({self.name}) has an unexpected stop process running"
            )

        # FIXME - before we "stop" a tool, check to see if a
        # "{tool}/{tool}.pid" file exists.  If it doesn't wait for a second to
        # show up, if after a second it does not show up, then give up waiting
        # and just call the stop method.
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
            f"{self.pbench_bin}/tool-scripts/{self.name}",
            "--stop",
            f"--dir={self.tool_dir}",
            self.tool_opts,
        ]
        self.logger.info("%s: stop_tool -- %s", self.name, " ".join(args))
        o_file = self.tool_dir / f"tm-{self.name}-stop.out"
        e_file = self.tool_dir / f"tm-{self.name}-stop.err"
        with o_file.open("w") as ofp, e_file.open("w") as efp:
            self.stop_process = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=ofp, stderr=efp
            )

    def wait(self):
        """Wait for any tool processes to terminate after a "stop" process has
        completed.

        Waits for the tool's "stop" process to complete, if started, then
        waits for the tool's start process to complete.
        """
        if self.stop_process is not None:
            if self.start_process is None:
                raise ToolException(
                    f"Tool({self.name}) does not have a start process running"
                )
            self.logger.info("waiting for stop %s", self.name)
            # We wait for the stop process to finish first ...
            self.stop_process.wait()
            self.stop_process = None
            # ... then we wait for the start process to finish
            self.start_process.wait()
            self.start_process = None
        else:
            raise ToolException(f"Tool({self.name}) wait not called after 'stop'")


class RedisDisconnected(Exception):
    """Simple exception to be raised when we lose the connection to the Redis
    server.
    """

    pass


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
            "channel":    "<Redis server channel name to subscribe to for"
                          " start/stop/send messages from controller>",
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
            channel = params["channel"]
            controller = params["controller"]
            group = params["group"]
            hostname = params["hostname"]
            tools = params["tools"]
        except KeyError as exc:
            raise ToolMeisterError(f"Invalid parameter block, missing key {exc}")
        else:
            return benchmark_run_dir, channel, controller, group, hostname, tools

    def __init__(
        self, pbench_bin, tar_path, sysinfo_dump, params, redis_server, logger
    ):
        self.pbench_bin = pbench_bin
        self.tar_path = tar_path
        self.sysinfo_dump = sysinfo_dump
        ret_val = self.fetch_params(params)
        (
            self._benchmark_run_dir,
            self._channel,
            self._controller,
            self._group,
            self._hostname,
            self._tools,
        ) = ret_val
        self._rs = redis_server
        self.logger = logger
        self.tool_metadata = toolmetadata.ToolMetadata(
            "redis", redis_server, self.logger
        )
        self.persist_tools = self.tool_metadata.getPersistentTools()
        self._running_tools = dict()
        self._persistent_tools = dict()
        logger.debug("pubsub")
        self._pubsub = self._rs.pubsub()
        logger.debug("subscribe %s", self._channel)
        self._pubsub.subscribe(self._channel)
        logger.debug("listen")
        self._chan = self._pubsub.listen()
        logger.debug("done listening")
        # Now that we have subscribed to the channel as specified in the
        # params object, we need to pull off the first message, which is an
        # acknowledgement that we have properly subscribed.
        logger.debug("next")
        resp = next(self._chan)
        assert resp["type"] == "subscribe", f"Unexpected 'type': {resp!r}"
        assert resp["pattern"] is None, f"Unexpected 'pattern': {resp!r}"
        assert (
            resp["channel"].decode("utf-8") == self._channel
        ), f"Unexpected 'channel': {resp!r}"
        assert resp["data"] == 1, f"Unexpected 'data': {resp!r}"
        logger.debug("next done")
        # We start in the "startup" state, waiting for first "init" action.
        self.state = "startup"
        self._valid_states = frozenset(["startup", "idle", "running", "shutdown"])
        self._state_trans = {
            "end": {"curr": "idle", "next": "shutdown", "action": self.end_tools},
            "init": {"curr": "startup", "next": "idle", "action": self.init_tools},
            "start": {"curr": "idle", "next": "running", "action": self.start_tools},
            "stop": {"curr": "running", "next": "idle", "action": self.stop_tools},
        }
        self._valid_actions = frozenset(
            ["end", "init", "send", "start", "stop", "sysinfo", "terminate"]
        )
        for key in self._state_trans.keys():
            assert (
                key in self._valid_actions
            ), f"INTERNAL ERROR: invalid state transition entry, '{key}'"
            assert self._state_trans[key]["next"] in self._valid_states, (
                "INTERNAL ERROR: invalid state transition 'next' entry for"
                f" '{key}', '{self._state_trans[key]['next']}'"
            )
        self._message_keys = frozenset(["action", "args", "directory", "group"])
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
        # The temporary directory to use for capturing all tool data.
        self._tmp_dir = os.environ["pbench_tmp"]

        # FIXME: run all the "--install" commands for the tools to ensure
        # they are successful before declaring that we are ready.

        # Tell the entity that started us who we are, indicating we're ready.
        started_msg = dict(kind="tm", hostname=self._hostname, pid=os.getpid())
        logger.debug("publish *-start")
        self._rs.publish(
            f"{self._channel}-start", json.dumps(started_msg, sort_keys=True)
        )
        logger.debug("published *-start")

    def cleanup(self):
        """cleanup - close down the Redis pubsub object."""
        self.logger.debug("%s: cleanup", self._hostname)
        if self._pubsub:
            self.logger.debug("unsubscribe")
            self._pubsub.unsubscribe()
            self.logger.debug("pubsub close")
            self._pubsub.close()

    def _get_data(self):
        """_get_data - fetch and decode the JSON object off the "wire".

        The keys in the JSON object are validated against the expected keys,
        and the value of the 'action' key is validated against the list of
        actions.
        """
        data = None
        while not data:
            self.logger.debug("next")
            try:
                payload = next(self._chan)
            except redis.ConnectionError as exc:
                try:
                    msg = exc.args[0]
                except Exception:
                    msg = ""
                if msg.startswith(SERVER_CLOSED_CONNECTION_ERROR):
                    # Redis disconnected, shutdown as gracefully as possible.
                    # FIXME: Consider adding connection drop error handling, retry loop
                    # re-establishing a connection, etc..
                    self._pubsub = None
                    raise RedisDisconnected()
                else:
                    raise
            else:
                self.logger.debug("next success")
            msg = None
            try:
                json_str = payload["data"].decode("utf-8")
                tmp_data = json.loads(json_str)
            except Exception:
                msg = f"data payload in message not JSON, {json_str!r}"
            else:
                keys = frozenset(tmp_data.keys())
                if keys != self._message_keys:
                    msg = (
                        f"unrecognized keys in data of payload in message, {json_str!r}"
                    )
                elif tmp_data["action"] not in self._valid_actions:
                    msg = f"unrecognized action in data of payload in message, {json_str!r}"
                elif tmp_data["group"] is not None and tmp_data["group"] != self._group:
                    msg = f"unrecognized group in data of payload in message, {json_str!r}"
                else:
                    data = tmp_data
            finally:
                if msg is not None:
                    assert data is None
                    self.logger.warning(msg)
                    self._send_client_status(msg)
        return data["action"], data

    def wait_for_command(self):
        """wait_for_command - wait for the expected data message for the
        current state

        Reads messages pulled from the wire, ignoring messages for unexpected
        actions, returning an (action_method, data) tuple when an expected
        state transition is encountered, and setting the next state properly.
        """
        self.logger.debug("%s: wait_for_command %s", self._hostname, self.state)
        action, data = self._get_data()
        action_method = None
        while not action_method:
            if action == "terminate":
                self.logger.debug("%s: msg - %r", self._hostname, data)
                raise Terminate()
            if action == "send":
                action_method = self.send_tools
                continue
            if action == "sysinfo":
                action_method = self.sysinfo
                continue
            state_trans_rec = self._state_trans[action]
            if state_trans_rec["curr"] != self.state:
                msg = f"ignoring unexpected data, {data!r}, in state '{self.state}'"
                self.logger.info(msg)
                self._send_client_status(msg)
                action, data = self._get_data()
                continue
            action_method = state_trans_rec["action"]
            self.state = state_trans_rec["next"]
        self.logger.debug("%s: msg - %r", self._hostname, data)
        return action_method, data

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
        msg = dict(kind="tm", hostname=self._hostname, status=status)
        self.logger.debug("publish tmc")
        try:
            num_present = self._rs.publish(
                client_channel, json.dumps(msg, sort_keys=True)
            )
        except Exception:
            self.logger.exception("Failed to publish client status message")
            ret_val = 1
        else:
            self.logger.debug("published tmc")
            if num_present != 1:
                self.logger.error(
                    "client status message received by %d subscribers", num_present
                )
                ret_val = 1
            else:
                self.logger.debug("posted client status, %r", status)
                ret_val = 0
        return ret_val

    def init_tools(self, data):
        """init_tools - setup all registered tools which have data collectors.

        The Tool Data Sink will be setting up the actual processes which
        collect data from these tools.
        """
        failures = 0
        tool_cnt = 0
        for name, tool_opts in self._tools.items():
            if name not in self.persist_tools:
                continue
            tool_cnt += 1
            try:
                persistent_tool = PersistentTool(name, tool_opts, self.logger)
                persistent_tool.start()

                self.logger.debug("NAME: " + name + "  TOOL OPTS: " + tool_opts)
            except Exception:
                self.logger.exception(
                    "Failed to init PersistentTool %s running in background", name
                )
                failures += 1
                continue
            else:
                self._persistent_tools[name] = persistent_tool
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
        self._tool_dir = _dir / self._hostname
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
            if name in self.persist_tools:
                continue
            tool_cnt += 1
            try:
                tool = Tool(
                    name,
                    self._group,
                    tool_opts,
                    self.pbench_bin,
                    self._tool_dir,
                    self.logger,
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
            if name in self.persist_tools:
                continue
            try:
                tool = self._running_tools[name]
            except KeyError:
                self.logger.error(
                    "INTERNAL ERROR - tool %s not found in list of running tools", name
                )
                failures += 1
                continue
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
            if name in self.persist_tools:
                continue
            tool_cnt += 1
            try:
                tool = self._running_tools[name]
            except KeyError:
                self.logger.error(
                    "INTERNAL ERROR - tool %s not found in list of running tools", name
                )
                failures += 1
                continue
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
            if name in self.persist_tools:
                continue
            try:
                del self._running_tools[name]
            except KeyError:
                self.logger.error(
                    "INTERNAL ERROR - tool %s not found in list of running tools", name,
                )
                failures += 1
                continue

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
        directory with a name that is the same as the self.hostname.

        The uri and ctx arguments are used to form the final URL as defined by:

           f"http://{self._controller}:8080/{uri}/{ctx}/{self._hostname}"

        """
        failures = 0
        parent_dir = directory.parent
        tar_file = parent_dir / f"{self._hostname}.tar.xz"
        o_file = parent_dir / f"{self._hostname}.tar.out"
        e_file = parent_dir / f"{self._hostname}.tar.err"
        try:
            # Invoke tar directly for efficiency.
            with o_file.open("w") as ofp, e_file.open("w") as efp:
                cp = subprocess.run(
                    [self.tar_path, "-Jcf", tar_file, self._hostname],
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

        if len(set(self._tools.keys()) - set(self.persist_tools)) == 0:
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
        for name in self._tools.keys():
            if name not in self.persist_tools:
                continue
            tool_cnt += 1
            try:
                persistent_tool = self._persistent_tools[name]
            except KeyError:
                self.logger.error(
                    "INTERNAL ERROR - tool %s not in list of persistent tools", name,
                )
                failures += 1
                continue
            try:
                persistent_tool.stop()
            except Exception:
                self.logger.exception(
                    "Failed to stop persistent tool %s running in background", name
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

        args = data["args"]
        if not args:
            self._send_client_status("No sysinfo arguments given")
            return 1

        self.logger.debug("sysinfo: %r", args)
        # FIXME - Should we perform more checking to validate the argument?
        sysinfo = args[0]
        # FIXME - We need the label for this registered host
        label = ""

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

        command = [
            self.sysinfo_dump,
            str(sysinfo_dir),
            sysinfo,
            label,
        ]

        self.logger.info("pbench-sysinfo-dump -- %s", " ".join(command))

        o_file = sysinfo_dir / "tm-sysinfo.out"
        e_file = sysinfo_dir / "tm-sysinfo.err"
        try:
            with o_file.open("w") as ofp, e_file.open("w") as efp:
                cp = subprocess.run(
                    command, cwd=sysinfo_dir, stdin=None, stdout=ofp, stderr=efp,
                )
        except Exception as exc:
            msg = f"Failed to collect system information: {exc}"
            self.logger.exception(msg)
            self._send_client_status(msg)
            return 1
        else:
            if cp.returncode != 0:
                msg = f"failed to collect system information; return code: {cp.returncode}"
                self.logger.error(msg)
                self._send_client_status(msg)
                return 1

        if self._hostname == self._controller:
            self.logger.info(
                "%s: sysinfo send (no-op) %s %s",
                self._hostname,
                self._group,
                sysinfo_dir,
            )
            # Note that we don't have a directory to send when a Tool
            # Meister runs on the same host as the controller.
            self._send_client_status("success")
            return 0

        directory_bytes = data["directory"].encode("utf-8")
        sysinfo_data_ctx = hashlib.md5(directory_bytes).hexdigest()
        failures = self._send_directory(
            sysinfo_dir / self._hostname, "sysinfo-data", sysinfo_data_ctx
        )

        self._send_client_status(
            "success" if failures == 0 else f"{failures} failures sending sysinfo data"
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
        sh = logging.SysLogHandler()
    sh.setLevel(log_level)
    shf = logging.Formatter(fmtstr_ut if unit_tests else fmtstr)
    sh.setFormatter(shf)
    logger.addHandler(sh)

    return logger


def driver(
    PROG,
    tar_path,
    sysinfo_dump,
    pbench_bin,
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
    rh = RedisHandler(
        channel="tm-logging", hostname=params["hostname"], redis_client=redis_server
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

    try:
        tm = ToolMeister(
            pbench_bin, tar_path, sysinfo_dump, params, redis_server, logger
        )
    except Exception:
        logger.exception(
            "Unable to construct the ToolMeister object with params, %r", params,
        )
        return 8

    ret_val = 0
    terminate = False
    try:
        while not terminate:
            try:
                logger.debug("waiting ...")
                action, data = tm.wait_for_command()
                logger.debug("acting ... %r, %r", action, data)
                failures = action(data)
                if failures > 0:
                    logger.warning(
                        "%d failures encountered for action, %r," " on data, %r",
                        failures,
                        action,
                        data,
                    )
            except Terminate:
                logger.info("terminating")
                terminate = True
            except RedisDisconnected:
                logger.error("lost connection to redis server")
                ret_val = 9
                terminate = True
    except Exception:
        logger.exception("Unexpected error encountered")
        ret_val = 10
    finally:
        tm.cleanup()
        if rh.errors > 0 or rh.redis_errors > 0:
            logger.warning(
                "RedisHandler redis_errors: %d, errors: %d", rh.errors, rh.redis_errors
            )
    return ret_val


def daemon(
    PROG,
    tar_path,
    sysinfo_dump,
    pbench_bin,
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

    pidfile_name = f"{param_key}.pid"
    pfctx = pidfile.PIDFile(pidfile_name)
    with open(f"{param_key}.out", "w") as sofp, open(
        f"{param_key}.err", "w"
    ) as sefp, DaemonContext(
        stdout=sofp,
        stderr=sefp,
        working_directory=os.getcwd(),
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
            return 7
        else:
            logger.debug("re-constructed Redis server object")
        return driver(
            PROG,
            tar_path,
            sysinfo_dump,
            pbench_bin,
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
    pbench_bin = _prog.parent.parent.parent

    try:
        redis_host = argv[1]
        redis_port = argv[2]
        param_key = argv[3]
    except IndexError as e:
        print(f"Invalid arguments: {e}", file=sys.stderr)
        return 1
    try:
        daemonize = argv[4]
    except IndexError:
        daemonize = "no"

    tar_path = find_executable("tar")
    if tar_path is None:
        print("External 'tar' executable not found.", file=sys.stderr)
        return 2

    sysinfo_dump = find_executable("pbench-sysinfo-dump")
    if sysinfo_dump is None:
        print("External 'pbench-sysinfo-dump' executable not found.", file=sys.stderr)
        return 3

    try:
        redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)
    except Exception as exc:
        print(
            f"Unable to construct Redis client, {redis_host}:{redis_port}: {exc}",
            file=sys.stderr,
        )
        return 4

    try:
        params_raw = redis_server.get(param_key)
        if params_raw is None:
            print(f'Parameter key, "{param_key}" does not exist.', file=sys.stderr)
            return 5
        params_str = params_raw.decode("utf-8")
        params = json.loads(params_str)
        # Validate the tool meister parameters without constructing an object
        # just yet, as we want to make sure we can talk to the redis server
        # before we go through the trouble of daemonizing below.
        ToolMeister.fetch_params(params)
    except Exception as exc:
        print(
            f"Unable to fetch and decode parameter key, '{param_key}': {exc}",
            file=sys.stderr,
        )
        return 6

    if daemonize == "yes":
        ret_val = daemon(
            PROG,
            tar_path,
            sysinfo_dump,
            pbench_bin,
            param_key,
            params,
            redis_server,
            redis_host,
            redis_port,
        )
    else:
        ret_val = driver(
            PROG, tar_path, sysinfo_dump, pbench_bin, param_key, params, redis_server
        )

    return ret_val
