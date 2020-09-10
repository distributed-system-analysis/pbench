import errno
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from distutils.spawn import find_executable
from pathlib import Path

import requests
import requests.exceptions

from pbench.server.utils import md5sum

# Path to external tar executable.
tar_path = find_executable("tar")

# FIXME: The client response channel should be in a shared constants module.
client_channel = "tool-meister-client"


class ToolException(Exception):
    pass


class Tool(object):
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
        self.screen_name = f"pbench-tool-{group}-{name}"
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
        """Creates the background `screen` process running the tool's "start"
        operation.
        """
        self._check_no_processes()
        # screen -dm -L -S \"${screen_name}\" ${pbench_bin}/tool-scripts/${name} --${action} --dir=${tool_output_dir} ${tool_opts[@]}
        args = [
            "/usr/bin/screen",
            "-dmS",
            self.screen_name,
            f"{self.pbench_bin}/tool-scripts/{self.name}",
            "--start",
            f"--dir={self.tool_dir}",
            self.tool_opts,
        ]
        self.logger.info("%s: start_tool -- %s", self.name, " ".join(args))
        self.start_process = subprocess.Popen(args)

    def stop(self):
        """Creates the background `screen` process to running the tool's "stop"
        operation.
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

        # $pbench_bin/tool-scripts/$name --$action --dir=${tool_output_dir} "${tool_opts[@]}"
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
                args, stdin=None, stdout=ofp, stderr=efp
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


class Terminate(Exception):
    """Simple exception to be raised when the tool meister main loop should exit
    gracefully.
    """

    pass


class ToolMeisterError(Exception):
    """Simple exception for any errors from the ToolMeister class.
    """

    pass


class ToolMeister(object):
    """Encapsulate tool life-cycle

    The goal of this class is to make sure all necessary state and behaviors
    for managing a given tool are handled by the methods offered by the
    class.

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

    def __init__(self, pbench_bin, params, redis_server, logger):
        self.logger = logger
        self.pbench_bin = pbench_bin
        ret_val = self.fetch_params(params)
        (
            self._benchmark_run_dir,
            self._channel,
            self._controller,
            self._group,
            self._hostname,
            self._tools,
        ) = ret_val
        self._running_tools = dict()
        self._rs = redis_server
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
        # We start in the "idle" state.
        self.state = "idle"
        self._valid_states = frozenset(["idle", "running"])
        self._state_trans = {
            "start": {"curr": "idle", "next": "running", "action": self.start_tools},
            "stop": {"curr": "running", "next": "idle", "action": self.stop_tools},
        }
        self._valid_actions = frozenset(["start", "stop", "send", "terminate"])
        for key in self._state_trans.keys():
            assert (
                key in self._valid_actions
            ), f"INTERNAL ERROR: invalid state transition entry, '{key}'"
            assert self._state_trans[key]["next"] in self._valid_states, (
                "INTERNAL ERROR: invalid state transition 'next' entry for"
                f" '{key}', '{self._state_trans[key]['next']}'"
            )
        self._message_keys = frozenset(["directory", "group", "action"])
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
        self._tmp_dir = os.environ.get("_PBENCH_TOOL_MEISTER_TMP", "/var/tmp")

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
        """cleanup - close down the Redis pubsub object.
        """
        self.logger.debug("%s: cleanup", self._hostname)
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
            except Exception:
                # FIXME: Add connection drop error handling, retry loop
                # re-establishing a connection.
                self.logger.exception("Error fetching 'next' data off channel")
            else:
                self.logger.debug("next success")
            try:
                json_str = payload["data"].decode("utf-8")
                data = json.loads(json_str)
            except Exception:
                self.logger.warning("data payload in message not JSON, %r", json_str)
                data = None
            else:
                keys = frozenset(data.keys())
                if keys != self._message_keys:
                    self.logger.warning(
                        "unrecognized keys in data of payload in message, %r", json_str,
                    )
                    data = None
                elif data["action"] not in self._valid_actions:
                    self.logger.warning(
                        "unrecognized action in data of payload in message, %r",
                        json_str,
                    )
                    data = None
                elif data["group"] is not None and data["group"] != self._group:
                    self.logger.warning(
                        "unrecognized group in data of payload in message, %r",
                        json_str,
                    )
                    data = None
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
        done = False
        while not done:
            if action == "terminate":
                self.logger.debug("%s: msg - %r", self._hostname, data)
                raise Terminate()
            if action == "send":
                self.logger.debug("%s: msg - %r", self._hostname, data)
                return self.send_tools, data
            state_trans_rec = self._state_trans[action]
            if state_trans_rec["curr"] != self.state:
                self.logger.info(
                    "ignoring unexpected data, %r, in state '%s'", data, self.state
                )
                action, data = self._get_data()
                continue
            done = True
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
            if failures == tool_cnt:
                msg = "failure"
            else:
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
                self.logger.error(
                    "INTERNAL ERROR - tool %s not found in list of running tools", name,
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
        for name in sorted(self._tools.keys()):
            try:
                tool = self._running_tools[name]
            except KeyError:
                self.logger.error(
                    "INTERNAL ERROR - tool %s not found in list of running tools", name,
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

        self._send_client_status(
            "success" if failures == 0 else "failures stopping tools"
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
            return False

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

        failures = 0
        parent_dir = tool_dir.parent
        tar_file = parent_dir / f"{self._hostname}.tar.xz"
        o_file = parent_dir / f"{self._hostname}.tar.out"
        e_file = parent_dir / f"{self._hostname}.tar.err"
        try:
            # Invoke tar directly for efficiency.
            with o_file.open("w") as ofp, e_file.open("w") as efp:
                cp = subprocess.run(
                    [tar_path, "-Jcf", tar_file, self._hostname],
                    cwd=parent_dir,
                    stdin=None,
                    stdout=ofp,
                    stderr=efp,
                )
        except Exception:
            self.logger.exception("Failed to create tools tar ball '%s'", tar_file)
        else:
            try:
                if cp.returncode != 0:
                    self.logger.error(
                        "Failed to create tools tar ball; return code: %d",
                        cp.returncode,
                    )
                    failures += 1
                else:
                    try:
                        tar_md5 = md5sum(tar_file)
                    except Exception:
                        self.logger.exception(
                            "Failed to read tools tar ball, '%s'", tar_file
                        )
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
                            "%s: starting send_tools %s %s",
                            self._hostname,
                            self._group,
                            self._directory,
                        )
                        headers = {"md5sum": tar_md5}
                        directory_bytes = data["directory"].encode("utf-8")
                        tool_data_ctx = hashlib.md5(directory_bytes).hexdigest()
                        url = f"http://{self._controller}:8080/tool-data/{tool_data_ctx}/{self._hostname}"
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
                                            "Failed to remove tool data hierarchy, '%s'",
                                            parent_dir,
                                        )
                                        failures += 1
                                    else:
                                        del self.directories[directory]
                        self.logger.info(
                            "%s: send_tools completed %s %s",
                            self._hostname,
                            self._group,
                            tool_dir,
                        )
            except Exception:
                self.logger.exception("Unexpected error encountered")
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
                        "error removing tools tar ball, '%s': %s", tar_file, exc
                    )
            except Exception as exc:
                self.logger.warning(
                    "unexpected error removing tools tar ball, '%s': %s", tar_file, exc,
                )

        self._send_client_status(
            "success" if failures == 0 else "failures sending tool data"
        )
        return failures


class ToolGroup(object):
    tg_prefix = "tools-v1"

    def __init__(self, group):
        self.group = group
        _pbench_run = os.environ["pbench_run"]
        self.tg_dir = Path(_pbench_run, f"{self.tg_prefix}-{self.group}").resolve(
            strict=True
        )
        if not self.tg_dir.is_dir():
            raise Exception(
                f"bad tool group, {group}: directory {self.tg_dir} does not exist"
            )

        # __trigger__
        try:
            _trigger = (self.tg_dir / "__trigger__").read_text()
        except OSError as ex:
            if ex.errno != errno.ENOENT:
                raise
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
            if host not in self.hostnames:
                self.hostnames[host] = {}
            for tdirent in os.listdir(self.tg_dir / host):
                if tdirent == "__label__":
                    self.labels[host] = (self.tg_dir / host / tdirent).read_text()
                    continue
                if tdirent.endswith("__noinstall__"):
                    # FIXME: ignore "noinstall" for now, tools are going to be
                    # in containers so this does not make sense going forward.
                    continue
                tool = tdirent
                tool_opts = (self.tg_dir / host / tool).read_text()
                if tool not in self.toolnames:
                    self.toolnames[tool] = {}
                self.toolnames[tool][host] = tool_opts

    def get_tools(self, host):
        """Given a target host, return a dictionary with the list of tool names
        as keys, and the values being their options for that host.
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
