#!/usr/bin/env python3

# Example curl command sequence
#
#   $ md5sum tool-data.tar.xz > tool-data.tar.xz.md5
#   $ curl -X PUT -H "MD5SUM: $(awk '{print $1}' tool-data.tar.xz.md5)" \
#     http://localhost:8080/tool-data/XXX...XXX/perf48.example.com \
#     --data-binary @tool-data.tar.xz

# Needs daemon, pidfile, and bottle
#   sudo dnf install python3-bottle python3-daemon
#   sudo pip3 install python-pidfile

import errno
import hashlib
import json
import logging
import os
import socket
import subprocess
import sys
import tempfile

from distutils.spawn import find_executable
from http import HTTPStatus
from pathlib import Path
from threading import Thread, Lock, Condition
from wsgiref.simple_server import WSGIRequestHandler, make_server

import daemon
import pidfile
import redis

from bottle import Bottle, ServerAdapter, request, abort

import pbench.agent.toolmetadata as toolmetadata


# Read in 64 KB chunks off the wire for HTTP PUT requests.
_BUFFER_SIZE = 65536

# Executable path of the tar program.
tar_path = None

# FIXME: move to a constants area, or a configuration setting.
client_channel = "tool-meister-client"

# FIXME: move to a constants area, or a configuration setting.
_MAX_TOOL_DATA_SIZE = 2 ** 30


class DataSinkWsgiServer(ServerAdapter):
    """DataSinkWsgiServer - an re-implementation of Bottle's WSGIRefServer
    where we have access to the underlying WSGIServer instance in order to
    invoke it's stop() method, and we also provide an WSGIReqeustHandler with
    an opinionated logging implementation.
    """

    def __init__(self, *args, logger=None, **kw):
        if logger is None:
            raise Exception("DataSinkWsgiServer requires a logger")
        super().__init__(*args, **kw)

        class DataSinkWsgiRequestHandler(WSGIRequestHandler):
            """DataSinkWsgiRequestHandler - a WSGIRequestHandler that uses the
            provided logger object.

            This basically closes over the logger parameter.
            """

            _logger = logger

            def log_error(self, format_str, *args):
                """log_error - log the error message with the client address"""
                self._logger.error(
                    "%s - - %s", self.address_string(), format_str % args
                )

            def log_message(self, format_str, *args):
                """log_message - log the message with the client address as a
                warning.
                """
                self._logger.warning(
                    "%s - - %s", self.address_string(), format_str % args
                )

            def log_request(self, code="-", size="-"):
                """log_request - log the request as an informational message."""
                if isinstance(code, HTTPStatus):
                    code = code.value
                self._logger.info(
                    '%s - - "%s" %s %s',
                    self.address_string(),
                    self.requestline,
                    str(code),
                    str(size),
                )

        self.options["handler_class"] = DataSinkWsgiRequestHandler
        self._server = None
        self._logger = logger

    def run(self, app):
        assert self._server is None, "'run' method called twice"
        self._logger.debug("Making tool data sink WSGI server ...")
        self._server = make_server(self.host, self.port, app, **self.options)
        self._logger.debug("Running tool data sink WSGI server ...")
        self._server.serve_forever()

    def stop(self):
        if self._server is not None:
            self._server.shutdown()


class BaseCollector:
    allowed_tools = {"noop-collector": None}

    def __init__(
        self, benchmark_run_dir, tool_group, host_tools_dict, logger, tool_metadata
    ):
        self.run = None
        self.benchmark_run_dir = benchmark_run_dir
        self.tool_group = tool_group
        self.host_tools_dict = host_tools_dict
        self.logger = logger
        self.tool_metadata = tool_metadata
        self.tool_group_dir = self.benchmark_run_dir / f"tools-{self.tool_group}"
        self.abort_launch = True

    def launch(self):
        pass

    def terminate(self):
        if self.abort_launch:
            return 0

        self.run.terminate()
        self.run.wait()
        return 1


class PromCollector(BaseCollector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.volume = self.tool_group_dir / "prometheus"

    def launch(self):

        if self.host_tools_dict:
            self.abort_launch = False
        else:
            return 0

        config = open("prometheus.yml", "w")

        config.write("global:\n  scrape_interval: 1s\n  evaluation_interval: 1s\n\n")
        # config.write("alerting:\n  alertmanagers:\n  - static_configs:\n    - targets:\n\nrule_files:\n\n")
        config.write(
            "scrape_configs:\n  - job_name: 'prometheus'\n    static_configs:\n    - targets: ['localhost:9090']\n\n"
        )

        for host in self.host_tools_dict:
            if host.startswith("local"):
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                host_ip = str(s.getsockname()[0])
                s.close()
            else:
                host_ip = host

            for tool in self.host_tools_dict[host]:
                port = self.tool_metadata.getProperties(tool)["port"]
                config.write(
                    "  - job_name: '{}_{}'\n    static_configs:\n    - targets: ['{}:{}']\n\n".format(
                        host_ip, tool, host_ip, port
                    )
                )

        config.close()

        prom_logs = open("prom.log", "w")

        if self.abort_launch:
            prom_logs.write("Prometheus launch aborted, no persistent tools registered")
            prom_logs.close()
            return 0

        args = ["podman", "pull", "prom/prometheus"]
        prom_pull = subprocess.Popen(args, stdout=prom_logs, stderr=prom_logs)
        prom_pull.wait()

        os.mkdir(self.volume)
        args = ["chmod", "777", self.volume]
        volume_dir = subprocess.Popen(args)
        volume_dir.wait()

        args = [
            "podman",
            "run",
            "-p",
            "9090:9090",
            "-v",
            f"{self.volume}:/prometheus:Z",
            "-v",
            f"{self.benchmark_run_dir}/tm/prometheus.yml:/etc/prometheus/prometheus.yml:Z",
            "prom/prometheus",
        ]
        self.run = subprocess.Popen(args, stdout=prom_logs, stderr=prom_logs)

        prom_logs.close()

        return 1

    def terminate(self):
        if super().terminate() == 0:
            return 0

        self.logger.debug("PROM TERMINATED")

        args = [
            "tar",
            "--remove-files",
            "--exclude",
            "prometheus/prometheus_data.tar.gz",
            "-zcvf",
            f"{self.volume}/prometheus_data.tar.gz",
            "-C",
            f"{self.tool_group_dir}/",
            "prometheus",
        ]
        data_store = subprocess.Popen(args)
        data_store.wait()

        return 1


class ToolDataSink(Bottle):
    """ToolDataSink - sub-class of Bottle representing state for tracking data
    sent from tool meisters via an HTTP PUT method.
    """

    class Terminate(Exception):
        pass

    def __init__(self, redis_server, channel, benchmark_run_dir, tool_group, logger):
        super(ToolDataSink, self).__init__()
        # Save external state
        self.redis_server = redis_server
        self.channel = channel
        self.benchmark_run_dir = benchmark_run_dir
        self.tool_group = tool_group
        self.logger = logger
        # Initialize internal state
        self._hostname = os.environ["full_hostname"]
        self.state = None
        self.tool_data_ctx = None
        self.directory = None
        self.tool_metadata = toolmetadata.ToolMetadata("redis", redis_server, logger)
        self._data = None
        self._prom_server = None
        self._tm_tracking = None
        self._lock = Lock()
        self._cv = Condition(lock=self._lock)
        # Setup the Bottle server route and the WSGI server instance.
        self.route(
            "/tool-data/<tool_data_ctx>/<hostname>",
            method="PUT",
            callback=self.put_document,
        )
        self._server = DataSinkWsgiServer(host="0.0.0.0", port=8080, logger=logger)
        # Setup the Redis server channel subscription
        logger.debug("pubsub")
        self._pubsub = redis_server.pubsub()
        logger.debug("subscribe %s", channel)
        self._pubsub.subscribe(channel)
        logger.debug("listen")
        self._chan = self._pubsub.listen()
        # Pull off first message which is an acknowledgement we have
        # successfully subscribed.
        logger.debug("next")
        resp = next(self._chan)
        assert resp["type"] == "subscribe", f"bad type: {resp!r}"
        assert resp["pattern"] is None, f"bad pattern: {resp!r}"
        assert resp["channel"].decode("utf-8") == channel, f"bad channel: {resp!r}"
        assert resp["data"] == 1, f"bad data: {resp!r}"
        logger.debug("next success")
        # Tell the entity that started us who we are indicating we're ready.
        started_msg = dict(kind="ds", hostname=self._hostname, pid=os.getpid())
        logger.debug("publish *-start")
        redis_server.publish(
            f"{channel}-start", json.dumps(started_msg, sort_keys=True)
        )
        logger.debug("published *-start")
        self.web_server_thread = None

    def run(self):
        """run - Start the Bottle web server running and the watcher thread."""
        self.logger.info("Running Bottle web server ...")
        try:
            super().run(server=self._server)
        except Exception:
            self.logger.exception("Exception encountered in Bottle web server")
        finally:
            self.logger.info("Bottle web server exited")

    def execute(self):
        """execute - Start the Bottle web server running and the watcher thread."""
        self.web_server_thread = Thread(target=self.run)
        self.web_server_thread.start()
        self.logger.debug("web server 'run' thread started, processing payloads ...")

        try:
            for payload in self._chan:
                self.logger.debug("payload")
                try:
                    json_str = payload["data"].decode("utf-8")
                except Exception:
                    self.logger.warning(
                        "data payload in message not UTF-8, '%r'", json_str
                    )
                    continue
                self.logger.debug('watcher: channel payload, "%r"', json_str)
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    self.logger.warning(
                        "data payload in message not JSON, '%s'", json_str
                    )
                    continue
                else:
                    try:
                        data["action"]
                    except KeyError:
                        self.logger.warning(
                            "unrecognized data payload in message, '%s'", json_str
                        )
                    else:
                        self.logger.debug("state change, %r", data)
                        self.state_change(data)
        except self.Terminate as exc:
            self.logger.info("%s", exc)
        except redis.exceptions.ConnectionError:
            self.logger.warning(
                "run closing down after losing connection to redis server"
            )
        except Exception:
            self.logger.exception("execute exception")
        finally:
            try:
                self._cleanup()
            except Exception:
                self.logger.exception("error(s) during cleanup")

    def _cleanup(self):
        """_cleanup - Encapsulates the proper shutdown sequence for the WSGI server
        and Redis Server connection.
        """
        self.logger.debug("unsubscribe")
        self._pubsub.unsubscribe()
        self.logger.debug("pubsub close")
        self._pubsub.close()
        self.logger.debug("web server stop")
        try:
            self._server.stop()
        except Exception:
            self.logger.exception("unexpected error stopping web server")
        self.logger.debug("Waiting for the web server thread to exit ...")
        try:
            self.web_server_thread.join()
        except Exception:
            pass

    def _fetch_tms(self):
        """_fetch_tms - fetch all the Tool Meister data for all recorded tool
        meisters in the Redis server under the tm-pids key.

        We return to the caller a dictionary indexed by the host name of each
        tool meister found.

        NOTE: this method should only be called when we know the "tm-pids" key
        is properly populated.
        """
        tms = {}
        self.logger.debug("get tm-pids")
        try:
            pids_json_str_raw = self.redis_server.get("tm-pids")
        except Exception:
            self.logger.exception("error fetching tm-pids")
            return tms
        else:
            self.logger.debug("get tm-pids success")
        if pids_json_str_raw is None:
            raise Exception("Missing 'tm-pids' data on Redis server")
        self.logger.debug("tm-pids: %r", pids_json_str_raw)
        try:
            pids_json_str = pids_json_str_raw.decode("utf-8")
            pids = json.loads(pids_json_str)
        except Exception as exc:
            raise Exception(f"failed parse 'tm-pids' JSON payload, '{exc}'")
        else:
            # Double check our data sink entry is as expected.
            assert pids["ds"]["kind"] == "ds", f"what? {pids['ds']!r}"
            assert pids["ds"]["pid"] == os.getpid(), f"what? {pids['ds']!r}"
            assert pids["ds"]["hostname"] == self._hostname, f"what? {pids['ds']!r}"
            for tm in pids["tm"]:
                assert tm["kind"] == "tm", f"what? {tm!r}"
                # Fetch all the tool data for this Tool Meister.
                tm_name = tm["hostname"]
                tools_json_str_raw = self.redis_server.get(
                    f"tm-{self.tool_group}-{tm_name}"
                )
                tools_json_str = tools_json_str_raw.decode("utf-8")
                tools = json.loads(tools_json_str)["tools"]
                noop_tools = []
                persistent_tools = []
                transient_tools = []
                for tool_name in tools.keys():
                    if tool_name in self.tool_metadata.getPersistentTools():
                        persistent_tools.append(tool_name)
                    elif tool_name in BaseCollector.allowed_tools:
                        noop_tools.append(tool_name)
                    elif tool_name in self.tool_metadata.getTransientTools():
                        transient_tools.append(tool_name)
                    else:
                        self.logger.error(
                            f"Registered tool {tool_name} is not recognized in tool metadata"
                        )
                tm["noop_tools"] = noop_tools
                tm["persistent_tools"] = persistent_tools
                tm["transient_tools"] = transient_tools

                if tm["hostname"] == self._hostname:
                    # The "localhost" tool meister instance does not send data
                    # to the tool data sink, it just writes it locally.
                    tm["posted"] = None
                elif not transient_tools:
                    # Only Tool Meisters with at least one transient tool will
                    # send data to a data sink, so ignore those Tool Meisters
                    # without any.
                    tm["posted"] = None
                else:
                    # The `posted` field is "dormant" to start (as set below),
                    # "waiting" when we transition to the "send" state, "dormant"
                    # when we receive data from the target Tool Meister host.
                    tm["posted"] = "dormant"
                tms[tm["hostname"]] = tm
        return tms

    def _wait_for_all_data(self):
        """wait_for_all_data - block the caller until all of the registered
        tool meisters have sent their data.

        Waiting is a no-op for all states except 'send'.  In the 'send' state,
        we are expecting to hear from all registered tool meisters.
        """
        assert self.state == "send", f"expected state 'send' not '{self.state}'"
        assert self._tm_tracking is not None, "Logic bomb!  self._tm_tracking is None"

        done = False
        while not done:
            for hostname, tm in self._tm_tracking.items():
                if tm["posted"] is None:
                    continue
                if tm["posted"] == "waiting":
                    # Don't bother checking any other Tool Meister when we
                    # have at least one that has not sent any data.
                    break
                assert tm["posted"] == "dormant", f"Logic bomb! {tm['posted']!r}"
            else:
                # We have checked every Tool Meister tracking record and
                # they all have posted their data (`posted` field is set
                # to "yes").  So we can safely exit the wait loop
                done = True
            if not done:
                self._cv.wait()
        return

    def _change_tm_tracking(self, curr, new):
        """_change_tm_tracking - if we have a tool meister tracking dictionary
        update the posted state from the current expected value to the target
        new value.

        No changes take place if the tool meister tracking dictionary does not
        exist yet.

        Assumes self._lock is already acquired by our caller.
        """
        if self._tm_tracking is None:
            return
        for hostname, tm in self._tm_tracking.items():
            if tm["posted"] is None:
                continue
            assert (
                tm["posted"] == curr
            ), f"_change_tm_tracking unexpected tm posted value, {tm!r}"
            tm["posted"] = new

    def state_change(self, data):
        """state_change - give a data dictionary, change the state for this
        data sink instance.

        The "watcher" thread has already validated the state field, we then
        validate the directory field.

        Public method, returns None, raises no exceptions explicitly, called
        by the "watcher" thread.
        """
        if self.state is None:
            # This is the first published state change we have received.
            with self._lock:
                assert self._tm_tracking is None, (
                    f"Logic bomb! self._tm_tracking '{self._tm_tracking!r}'"
                    " is not None"
                )
                # Typically, we only call this method once when the Tool Data
                # Sink first starts since the list of Tool Meister's is
                # static.  We call it when we get the first message to
                # be sure the "tm-pids" key exists.
                #
                # FIXME: what happens when a Tool Meister dies, and rejoins?
                self._tm_tracking = self._fetch_tms()

        self._data = data
        self.state = data["action"]
        if self.state == "terminate":
            raise self.Terminate("Terminate bottle server")
        directory_str = data["directory"]
        directory = Path(directory_str)
        if not directory.is_dir():
            self.logger.error(
                "state change to '%s' with non-existent directory, '%s'",
                data["action"],
                directory,
            )
            raise self.Terminate("Terminate bottle server w/ error")
        try:
            # Check that "directory" has a prefix of self.benchmark_run_dir
            directory.relative_to(self.benchmark_run_dir)
        except ValueError:
            self.logger.error(
                "state change to '%s' with invalid directory,"
                " '%s' (not a sub-directory of '%s')",
                data["action"],
                directory,
                self.benchmark_run_dir,
            )
            raise self.Terminate("Terminate bottle server w/ error")
        else:
            self.directory = directory
        # The remote tool meisters will be hashing the directory argument this
        # way when invoking the PUT method.  They just consider the directory
        # argument to be an opaque context.  We, the tool data sink, write the
        # data we receive to that directory, but expect them to provide the
        # opaque context in the URL for the PUT method.
        directory_bytes = directory_str.encode("utf-8")
        self.tool_data_ctx = hashlib.md5(directory_bytes).hexdigest()

        # Transition to "send" state should reset self._tm_tracking
        with self._lock:
            if self.state == "init":
                prom_tool_dict = {}
                for tm in self._tm_tracking:
                    prom_tools = []
                    persist_tools = self._tm_tracking[tm]["persistent_tools"]
                    for tool in persist_tools:
                        tool_data = self.tool_metadata.getProperties(tool)
                        if tool_data["collector"] == "prometheus":
                            prom_tools.append(tool)
                    if len(prom_tools) > 0:
                        prom_tool_dict[self._tm_tracking[tm]["hostname"]] = prom_tools
                self.logger.debug(prom_tool_dict)

                if prom_tool_dict:
                    self._prom_server = PromCollector(
                        self.benchmark_run_dir,
                        self.tool_group,
                        prom_tool_dict,
                        self.logger,
                        self.tool_metadata,
                    )
                    self._prom_server.launch()
            elif self.state == "end":
                if self._prom_server:
                    self._prom_server.terminate()
            elif self.state == "send":
                self._change_tm_tracking("dormant", "waiting")
                # The Tool Data Sink cannot send success until all the Tool
                # Meisters have sent their collected data, so wait for all the
                # tool meisters before proceeding.
                self._wait_for_all_data()
                # At this point all tracking data should be "dormant" again.
            else:
                assert self.state in (
                    "start",
                    "stop",
                ), f"Unexpected state, '{self.state}'"
                # Nothing to do, no data movement for "start" or "stop";
                # FIXME: we should assert that all Tool Meister's tracking
                # data is "dormant".

        self._send_client_status("success")

    def _send_client_status(self, status):
        """_send_client_status - encapsulate sending back the status message to
        the client.

        Returns 0 on success, 1 on failure, logging any exceptions encountered.
        """
        # The published client status message contains three pieces of
        # information:
        #   {
        #     "kind": "ds|tm",
        #     "hostname": "< the host name on which the ds or tm is running >",
        #     "status": "success|< a message to be displayed on error >"
        #   }
        msg = dict(kind="ds", hostname=self._hostname, status=status)
        self.logger.debug("publish tmc")
        try:
            num_present = self.redis_server.publish(
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

    def put_document(self, tool_data_ctx, hostname):
        """put_document - PUT callback method for Bottle web server end point

        The put_document method is called by threads serving web requests.
        There can be N threads configured at one time calling this method.

        Public method, returns None, raises no exceptions directly, calls the
        Bottle abort() method for error handling.

        """
        with self._lock:
            if self.state != "send":
                # FIXME: Don't we have a race condition if the tool meisters
                # process their messages first?  Seems like we need to send to
                # the Tool Data Sink first, and then send to all the tool
                # meisters.
                abort(400, f"Can't accept PUT requests in state '{self.state}'")
            if self.tool_data_ctx != tool_data_ctx:
                # Tool Data Sink and this Tool Meister are out of sink as to
                # what data is expected.
                abort(400, f"Unexpected tool data context, '{tool_data_ctx}'")
            # Fetch the Tool Meister tracking record for this host and verify
            # it is in the expected waiting state.
            tm_tracker = self._tm_tracking[hostname]
            if tm_tracker["posted"] != "waiting":
                self.logger.error(
                    "INTERNAL ERROR: expected Tool Meister for host, %s, in"
                    " `waiting` state, found in `%s` state",
                    hostname,
                    tm_tracker["posted"],
                )
                abort(400, "No data expected from a Tool Meister")

        try:
            content_length = int(request["CONTENT_LENGTH"])
        except ValueError:
            abort(400, "Invalid content-length header, not an integer")
        except Exception:
            abort(400, "Missing required content-length header")
        else:
            if content_length > _MAX_TOOL_DATA_SIZE:
                abort(
                    400,
                    "Content object too large, keep it at 1 GB"
                    f" ({content_length:d}) and  under",
                )
            remaining_bytes = content_length

        try:
            exp_md5 = request["HTTP_MD5SUM"]
        except Exception:
            self.logger.exception(request.keys())
            abort(400, "Missing required md5sum header")

        target_dir = self.directory
        if not target_dir.is_dir():
            self.logger.error("ERROR - directory, '%s', does not exist", target_dir)
            abort(500, f"Invalid URL, path {target_dir} does not exist")
        host_tool_data_tb_name = target_dir / f"{hostname}.tar.xz"
        if host_tool_data_tb_name.exists():
            abort(409, f"{host_tool_data_tb_name} already uploaded")
        host_tool_data_tb_md5 = Path(f"{host_tool_data_tb_name}.md5")

        with tempfile.NamedTemporaryFile(mode="wb", dir=target_dir) as ofp:
            total_bytes = 0
            iostr = request["wsgi.input"]
            h = hashlib.md5()
            while remaining_bytes > 0:
                buf = iostr.read(
                    _BUFFER_SIZE if remaining_bytes > _BUFFER_SIZE else remaining_bytes
                )
                bytes_read = len(buf)
                total_bytes += bytes_read
                remaining_bytes -= bytes_read
                h.update(buf)
                ofp.write(buf)
            cur_md5 = h.hexdigest()
            if cur_md5 != exp_md5:
                abort(
                    400,
                    f"Content, {cur_md5}, does not match its MD5SUM header,"
                    f" {exp_md5}",
                )
            if total_bytes <= 0:
                abort(400, "No data received")

            # First write the .md5
            try:
                with host_tool_data_tb_md5.open("w") as md5fp:
                    md5fp.write(f"{exp_md5} {host_tool_data_tb_name.name}\n")
            except Exception:
                try:
                    os.remove(host_tool_data_tb_md5)
                except Exception as exc:
                    self.logger.warning(
                        "Failed to remove .md5 %s when trying to clean up: %s",
                        host_tool_data_tb_md5,
                        exc,
                    )
                self.logger.exception(
                    "Failed to write .md5 file, '%s'", host_tool_data_tb_md5
                )
                raise

            # Then create the final filename link to the temporary file.
            try:
                os.link(ofp.name, host_tool_data_tb_name)
            except Exception:
                try:
                    os.remove(host_tool_data_tb_md5)
                except Exception as exc:
                    self.logger.warning(
                        "Failed to remove .md5 %s when trying to clean up: %s",
                        host_tool_data_tb_md5,
                        exc,
                    )
                self.logger.exception(
                    "Failed to rename tar ball '%s' to '%s'",
                    ofp.name,
                    host_tool_data_tb_md5,
                )
                raise
            else:
                self.logger.debug(
                    "Successfully wrote %s (%s.md5)",
                    host_tool_data_tb_name,
                    host_tool_data_tb_name,
                )

        # Now unpack that tar ball
        o_file = target_dir / f"{hostname}.tar.out"
        e_file = target_dir / f"{hostname}.tar.err"
        try:
            # Invoke tar directly for efficiency.
            with o_file.open("w") as ofp, e_file.open("w") as efp:
                cp = subprocess.run(
                    [tar_path, "-xf", host_tool_data_tb_name],
                    cwd=target_dir,
                    stdin=None,
                    stdout=ofp,
                    stderr=efp,
                )
        except Exception:
            self.logger.exception(
                "Failed to extract tools tar ball, '%s'", host_tool_data_tb_name
            )
            raise
        else:
            if cp.returncode != 0:
                self.logger.error(
                    "Failed to create tools tar ball; return code: %d", cp.returncode
                )
                abort(500, "INTERNAL ERROR")
            else:
                self.logger.debug("Successfully unpacked %s", host_tool_data_tb_name)
                try:
                    o_file.unlink()
                    e_file.unlink()
                    host_tool_data_tb_md5.unlink()
                    host_tool_data_tb_name.unlink()
                except Exception:
                    self.logger.exception(
                        "Error removing unpacked tar ball '%s' and it's .md5",
                        host_tool_data_tb_name,
                    )

        # Tell the waiting "watcher" thread engaging in a "state" change
        # that another PUT document has arrived.
        with self._lock:
            tm_tracker = self._tm_tracking[hostname]
            assert tm_tracker["posted"] == "waiting", f"tm_tracker = {tm_tracker!r}"
            tm_tracker["posted"] = "dormant"
            self._cv.notify()


def main(argv):
    PROG = Path(argv[0]).name

    logger = logging.getLogger(PROG)
    fh = logging.FileHandler(f"{PROG}.log")
    if os.environ.get("_PBENCH_UNIT_TESTS"):
        fmtstr = "%(levelname)s %(name)s %(funcName)s -- %(message)s"
    else:
        fmtstr = (
            "%(asctime)s %(levelname)s %(process)s %(thread)s"
            " %(name)s %(funcName)s %(lineno)d -- %(message)s"
        )
    fhf = logging.Formatter(fmtstr)
    fh.setFormatter(fhf)
    if os.environ.get("_PBENCH_TOOL_DATA_SINK_LOG_LEVEL") == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    fh.setLevel(log_level)
    logger.addHandler(fh)
    logger.setLevel(log_level)

    try:
        redis_host = argv[1]
        redis_port = argv[2]
        param_key = argv[3]
    except IndexError as e:
        logger.error("Invalid arguments: %s", e)
        return 1

    global tar_path
    tar_path = find_executable("tar")
    if tar_path is None:
        logger.error("External 'tar' executable not found")
        return 2

    try:
        redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)
    except Exception as e:
        logger.error(
            "Unable to connect to redis server, %s:%s: %s", redis_host, redis_port, e
        )
        return 3

    try:
        params_raw = redis_server.get(param_key)
        if params_raw is None:
            logger.error('Parameter key, "%s" does not exist.', param_key)
            return 4
        logger.debug("params_key (%s): %r", param_key, params_raw)
        params_str = params_raw.decode("utf-8")
        # The expected parameters for this "data-sink" is what "channel" to
        # subscribe to for the tool meister operational life-cycle.  The
        # data-sink listens for the state transitions, start | stop | send |
        # terminate, exiting when "terminate" is received, marking the state
        # in which data is captured.
        #
        # E.g. params = '{ "channel": "run-chan",
        #                  "benchmark_run_dir": "/loo/goo" }'
        params = json.loads(params_str)
        channel = params["channel"]
        benchmark_run_dir = Path(params["benchmark_run_dir"]).resolve(strict=True)
        tool_group = params["group"]
    except Exception as ex:
        logger.error("Unable to fetch and decode parameter key, %s: %s", param_key, ex)
        return 5
    else:
        if not benchmark_run_dir.is_dir():
            logger.error(
                "Run directory argument, %s, must be a real directory.",
                benchmark_run_dir,
            )
            return 6
        logger.debug("Tool Data Sink parameters check out, daemonizing ...")
        redis_server.connection_pool.disconnect()
        del redis_server

    # Before we daemonize, flush any data written to stdout or stderr.
    sys.stderr.flush()
    sys.stdout.flush()

    pidfile_name = f"{PROG}.pid"
    pfctx = pidfile.PIDFile(pidfile_name)
    with open(f"{PROG}.out", "w") as sofp, open(
        f"{PROG}.err", "w"
    ) as sefp, daemon.DaemonContext(
        stdout=sofp,
        stderr=sefp,
        working_directory=os.getcwd(),
        umask=0o022,
        pidfile=pfctx,
        files_preserve=[fh.stream.fileno()],
    ):
        try:
            # We have to re-open the connection to the redis server now that we
            # are "daemonized".
            logger.debug("constructing Redis() object")
            try:
                redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)

            except Exception as e:
                logger.error(
                    "Unable to connect to redis server, %s:%s: %s",
                    redis_host,
                    redis_port,
                    e,
                )
                return 7
            else:
                logger.debug("constructed Redis() object")

            tds_app = ToolDataSink(
                redis_server, channel, benchmark_run_dir, tool_group, logger
            )
            tds_app.execute()
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                logger.error(
                    "ERROR - tool data sink failed to start, 0.0.0.0:8080 already in use"
                )
            else:
                logger.exception("ERROR - failed to start the tool data sink")
        except Exception:
            logger.exception("ERROR - failed to start the tool data sink")
        finally:
            logger.info("Remove pid file ... (%s)", pidfile_name)
            try:
                os.unlink(pidfile_name)
            except Exception:
                logger.exception("Failed to remove pid file %s", pidfile_name)

    return 0


if __name__ == "__main__":
    status = main(sys.argv)
    sys.exit(status)
