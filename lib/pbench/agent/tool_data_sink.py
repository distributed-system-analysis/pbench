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
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from configparser import ConfigParser, DuplicateSectionError
from datetime import datetime
from distutils.spawn import find_executable
from http import HTTPStatus
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from threading import Thread, Lock, Condition
from wsgiref.simple_server import WSGIRequestHandler, make_server

import daemon
import pidfile
import redis

from bottle import Bottle, ServerAdapter, request, abort

from pbench.agent import PbenchAgentConfig
from pbench.agent.constants import (
    tds_port,
    tm_allowed_actions,
    tm_channel_suffix_from_client,
    tm_channel_suffix_from_tms,
    tm_channel_suffix_to_client,
    tm_channel_suffix_to_logging,
    tm_channel_suffix_to_tms,
)
from pbench.agent.redis import RedisChannelSubscriber
from pbench.agent.toolmetadata import ToolMetadata
from pbench.agent.utils import collect_local_info


# Read in 64 KB chunks off the wire for HTTP PUT requests.
_BUFFER_SIZE = 65536

# Maximum size of the tar ball for collected tool data.
_MAX_TOOL_DATA_SIZE = 2 ** 30

# Executable path of the tar, cp, and podman programs.
tar_path = None
cp_path = None
podman_path = None


def _now(when):
    """_now - An ugly hack to facility testing without the ability to mock.

    Instead of directly calling `datatime.utcnow().isoformat()`, each call
    site invokes this method with an argument only used during unit testing
    to determine the expected behavior.  This allows us to provide a "start"
    time that is one microsecond less than the "end" time.
    """
    if os.environ.get("_PBENCH_UNIT_TESTS"):
        suf = "42" if when == "start" else "43"
        return f"1900-01-01T00:00:00.0000{suf}"
    else:
        return datetime.utcnow().isoformat()


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
        self._lock = Lock()
        self._cv = Condition(lock=self._lock)
        self._logger = logger

    def run(self, app):
        assert self._server is None, "'run' method called twice"
        self._logger.debug("Making tool data sink WSGI server ...")
        server = make_server(self.host, self.port, app, **self.options)
        with self._lock:
            self._server = server
            self._cv.notify()
        self._logger.debug("Running tool data sink WSGI server ...")
        self._server.serve_forever()

    def stop(self):
        with self._lock:
            while self._server is None:
                self._cv.wait()
        self._server.shutdown()


class BaseCollector:
    """Abstract class for persistent tool data collectors"""

    allowed_tools = {"noop-collector": None}

    def __init__(
        self,
        pbench_bin,
        benchmark_run_dir,
        tool_group,
        host_tools_dict,
        tool_metadata,
        logger,
    ):
        """Constructor - responsible for recording the arguments, and creating
        the Environment() for template rendering.
        """
        self.run = None
        self.benchmark_run_dir = benchmark_run_dir
        self.tool_group = tool_group
        self.host_tools_dict = host_tools_dict
        self.tool_metadata = tool_metadata
        self.logger = logger
        self.tool_group_dir = self.benchmark_run_dir / f"tools-{self.tool_group}"
        self.template_dir = Environment(
            autoescape=False,
            loader=FileSystemLoader(pbench_bin / "templates"),
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def launch(self):
        """launch - Abstract method for launching a persistent tool data
        collector.

        Must be overriden by the sub-class.
        """
        assert False, "Must be overriden by sub-class"

    def render_from_template(self, template, context):
        """render_from_template - Helper method used to generate the contents
        of a file given a Jinja template and its required context.

        Returns a string representing the contents of a file, or None if the
        rendering from the template failed.
        """
        try:
            filled = self.template_dir.get_template(template).render(context)
        except Exception as exc:
            self.logger.error(
                "template, %s, failed to render with context, %r: %r",
                template,
                context,
                exc,
            )
            return None
        else:
            return filled

    def terminate(self):
        """terminate - shutdown the persistent tool collector.

        Raises an exception on failure.
        """
        if not self.run:
            return
        try:
            self.run.terminate()
            self.run.wait()
        except Exception as exc:
            self.logger.error(
                "Failed to terminate expected collector process: '%s'", exc
            )
            raise


class PromCollector(BaseCollector):
    """Persistent tool data collector for tools compatible with Prometheus"""

    def __init__(self, *args, **kwargs):
        """Constructor - responsible for setting up the particulars for the
        Prometheus collector, including how to instruct prometheus to gather
        tool data.
        """
        super().__init__(*args, **kwargs)
        self.volume = self.tool_group_dir / "prometheus"
        self.tool_context = []
        for host, tools in sorted(self.host_tools_dict.items()):
            for tool in sorted(tools):
                port = self.tool_metadata.getProperties(tool)["port"]
                self.tool_context.append(
                    dict(hostname=f"{host}_{tool}", hostport=f"{host}:{port}")
                )
        if not self.tool_context:
            raise Exception("Expected prometheus persistent tool context not found")
        try:
            prom_reg = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"]).prom_reg
        except Exception as exc:
            raise Exception(
                "Unexpected error encountered fetch pbench agent"
                f" configuration: '{exc}'",
            )
        else:
            self.prom_reg = prom_reg

    def launch(self):
        """launch - creates the YAML file that directs Prometheus's behavior,
        the directory prometheus will write its data, and creates the sub-
        process that runs Prometheus.
        """
        yml = self.render_from_template("prometheus.yml", dict(tools=self.tool_context))
        assert yml is not None, f"Logic bomb!  {self.tool_context!r}"
        with open("prometheus.yml", "w") as config:
            config.write(yml)

        with open("prom.log", "w") as prom_logs:
            args = [podman_path, "pull", self.prom_reg]
            try:
                prom_pull = subprocess.Popen(args, stdout=prom_logs, stderr=prom_logs)
                prom_pull.wait()
            except Exception as exc:
                self.logger.error("Podman pull process failed: '%s'", exc)
                return

            try:
                os.mkdir(self.volume)
                os.chmod(self.volume, 0o777)
            except Exception as exc:
                self.logger.error("Volume creation failed: '%s'", exc)
                return

            args = [
                podman_path,
                "run",
                "-p",
                "9090:9090",
                "-v",
                f"{self.volume}:/prometheus:Z",
                "-v",
                f"{self.benchmark_run_dir}/tm/prometheus.yml:/etc/prometheus/prometheus.yml:Z",
                "--network",
                "host",
                self.prom_reg,
            ]
            try:
                self.run = subprocess.Popen(args, stdout=prom_logs, stderr=prom_logs)
            except Exception as exc:
                self.logger.error("Podman run process failed: '%s', %r", exc, args)
                self.run = None

    def terminate(self):
        """terminate - shuts down the prometheus sub-process, and creates a
        tar ball of the data collected.
        """
        try:
            super().terminate()
        except Exception:
            self.logger.error("Prometheus failed to terminate")
            return

        self.logger.debug("Prometheus terminated")

        args = [
            tar_path,
            "--remove-files",
            "-zcf",
            f"{self.tool_group_dir}/prometheus_data.tar.gz",
            "-C",
            f"{self.tool_group_dir}/",
            "prometheus",
        ]
        data_store = subprocess.Popen(args)
        data_store.wait()


class PCPCollector(BaseCollector):
    """Persistent tool data collector for tools compatible with Prometheus"""

    def __init__(self, *args, **kwargs):
        """Constructor - responsible for setting up the state needed to run
        the PCP collector.
        """
        super().__init__(*args, **kwargs)
        self.volume = self.tool_group_dir / "pcp"
        benchmark_run_dir_bytes = str(self.benchmark_run_dir).encode("utf-8")
        suffix = hashlib.md5(benchmark_run_dir_bytes).hexdigest()
        self.podname = f"collector-{suffix}"

    def __test_conn(self):
        # FIXME - embed this in the PCP image itself
        if os.environ.get("_PBENCH_UNIT_TESTS"):
            return 1
        test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for host in self.host_tools_dict:
            counter = 0
            while counter < 3:
                check = (host, 44321)
                if test.connect_ex(check) == 0:
                    break
                else:
                    counter += 1
                    if counter == 3:
                        self.logger.error(f"{host} pmcd unreachable")
                time.sleep(1)
        return 1

    def launch(self):
        """launch - responsible for creating the configuration file for
        collecting data from the register hosts, creates the directory for
        storing the collected data, and runs the PCP collector itself.
        """
        global podman_path
        pcp_remote_config = self.benchmark_run_dir / "tm" / "remote"
        with open(pcp_remote_config, "w") as remote:
            for host in self.host_tools_dict:
                remote.write(
                    f"{host} n n PCP_LOG_DIR/pmlogger/{host} -r -T24h10m -c config.{host}\n"
                )

        if not self.host_tools_dict:
            return

        with open("pcp.log", "w") as pcp_logs:
            try:
                pcp_reg = PbenchAgentConfig(
                    os.environ["_PBENCH_AGENT_CONFIG"]
                ).pmlogger_reg
            except Exception as exc:
                self.logger.error(
                    "Unexpected error encountered logging pbench agent configuration: '%s'",
                    exc,
                )
                return

            args = [podman_path, "pull", pcp_reg]
            try:
                pcp_pull = subprocess.Popen(args, stdout=pcp_logs, stderr=pcp_logs)
                pcp_pull.wait()
            except Exception as exc:
                self.logger.error("Podman pull process failed: '%s'", exc)
                return

            try:
                os.mkdir(self.volume)
                os.chmod(self.volume, 0o777)
            except Exception as exc:
                self.logger.error("Volume creation failed: '%s'", exc)
                return
            args = [
                podman_path,
                "run",
                "--systemd",
                "always",
                "-v",
                f"{self.volume}:/var/log/pcp/pmlogger:Z",
                "-v",
                f"{pcp_remote_config}:/etc/pcp/pmlogger/control.d/remote:Z",
                "--network",
                "host",
                "--name",
                self.podname,
                pcp_reg,
            ]
            try:
                self.__test_conn()
                self.run = subprocess.Popen(args, stdout=pcp_logs, stderr=pcp_logs)
            except Exception as exc:
                self.logger.error("Podman run process failed: '%s', %r", exc, args)
                self.run = None

    def terminate(self):
        """terminate - shuts down the PCP collector, and creates a tar ball of
        the collected data.
        """
        global podman_path
        if self.run:
            args = [
                podman_path,
                "kill",
                self.podname,
            ]
            try:
                pcp_kill = subprocess.Popen(args)
                pcp_kill.wait()
            except Exception as exc:
                self.logger.error("Podman kill process failed: '%s'", exc)
                return

        try:
            super().terminate()
        except Exception:
            self.logger.error("Pmlogger failed to terminate")
            return

        self.logger.debug("Pmlogger terminated")

        args = [
            tar_path,
            "--remove-files",
            "-zcf",
            f"{self.tool_group_dir}/pcp_data.tar.gz",
            "-C",
            f"{self.tool_group_dir}/",
            "pcp",
        ]
        data_store = subprocess.Popen(args)
        data_store.wait()


class ToolDataSink(Bottle):
    """ToolDataSink - sub-class of Bottle representing state for tracking data
    sent from tool meisters via an HTTP PUT method.
    """

    # The list of actions where we expect Tool Meisters to send data to us.
    _data_actions = frozenset(("send", "sysinfo"))

    def __init__(
        self,
        pbench_bin,
        hostname,
        bind_hostname,
        redis_server,
        channel_prefix,
        benchmark_run_dir,
        tool_group,
        tool_trigger,
        tools,
        tool_metadata,
        optional_md,
        logger,
    ):
        """Constructor for the Tool Data Sink object - responsible for
        recording parameters, and setting up initial state.

        """
        super(ToolDataSink, self).__init__()
        # Save external state
        self.pbench_bin = pbench_bin
        self.hostname = hostname
        self.bind_hostname = bind_hostname
        self.redis_server = redis_server
        self.channel_prefix = channel_prefix
        self.benchmark_run_dir = benchmark_run_dir
        self.tool_group = tool_group
        self.tool_trigger = tool_trigger
        self.tools = tools
        self.tool_metadata = tool_metadata
        self.optional_md = optional_md
        self.logger = logger
        # Initialize internal state
        self.action = None
        self.data_ctx = None
        self.directory = None
        self._server = None
        self._prom_server = None
        self._pcp_server = None
        self._tm_tracking = None
        self._to_logging_channel = (
            f"{self.channel_prefix}-{tm_channel_suffix_to_logging}"
        )
        self._to_tms_channel = f"{self.channel_prefix}-{tm_channel_suffix_to_tms}"
        self._from_tms_channel = f"{self.channel_prefix}-{tm_channel_suffix_from_tms}"
        self._to_client_channel = f"{self.channel_prefix}-{tm_channel_suffix_to_client}"
        self._from_client_channel = (
            f"{self.channel_prefix}-{tm_channel_suffix_from_client}"
        )
        self._lock = Lock()
        self._cv = Condition(lock=self._lock)
        self.web_server_thread = None
        self.tm_log_capture_thread = None

    def __enter__(self):
        # Setup the Bottle server route and the WSGI server instance.
        self.route(
            "/tool-data/<data_ctx>/<hostname>",
            method="PUT",
            callback=self.put_document,
        )
        self.route(
            "/sysinfo-data/<data_ctx>/<hostname>",
            method="PUT",
            callback=self.put_document,
        )
        self._server = DataSinkWsgiServer(
            host=self.bind_hostname, port=tds_port, logger=self.logger
        )
        self.web_server_thread = Thread(target=self.web_server_run)
        self.web_server_thread.start()
        # FIXME - ugly hack for consistent unit tests; why not just use a
        # condition variable?
        time.sleep(0.1)
        self.logger.debug("web server 'run' thread started, processing payloads ...")

        # Setup the two Redis channels to which the Tool Data Sink subscribes.
        self._from_tms_chan = RedisChannelSubscriber(
            self.redis_server, self._from_tms_channel
        )
        self._from_client_chan = RedisChannelSubscriber(
            self.redis_server, self._from_client_channel
        )

        # Setup the Redis channel use for logging by the Tool Meisters.
        self._to_logging_chan = RedisChannelSubscriber(
            self.redis_server, self._to_logging_channel
        )

        self.tm_log_capture_thread = Thread(target=self.tm_log_capture)
        self.tm_log_capture_thread.start()
        # FIXME - ugly hack for consistent unit tests; why not just use a
        # condition variable?
        time.sleep(0.1)
        self.logger.debug("'tm_log_capture' thread started, processing logs ...")

        # The ToolDataSink object itself is the object of the context manager.
        return self

    def __exit__(self, *args):
        """Context Manager exit - Encapsulates the proper shutdown sequence for the
        WSGI server and Redis Server connection.
        """
        self._from_tms_chan.close()
        self._from_client_chan.close()

        self.logger.debug("web server stop")
        try:
            self._server.stop()
        except Exception:
            self.logger.exception("unexpected error stopping web server")
        self.logger.debug("Waiting for the web server thread to exit ...")
        try:
            self.web_server_thread.join()
        except Exception:
            self.logger.exception("Errors joining with web server thread on exit")

        self.logger.debug("Waiting for the log capture thread to exit ...")
        try:
            self.tm_log_capture_thread.join()
        except Exception:
            self.logger.exception("Error joining with the log capture thread on exit")
        else:
            self.logger.debug("Exiting Tool Data Sink context ...")

    def web_server_run(self):
        """web_server_run - Start the Bottle web server running.
        """
        self.logger.info("Running Bottle web server ...")
        try:
            super().run(server=self._server)
        except Exception:
            self.logger.exception("Exception encountered in Bottle web server")
        finally:
            self.logger.info("Bottle web server exited")

    def tm_log_capture(self):
        """tm_log_capture - capture all logs written by local and remote Tool
        Meisters through the Redis server into one file.
        """
        self.logger.info("Running Tool Meister log capture ...")
        # Create a separate logger so that the fetch_message() code only logs
        # warnings and errors to stdout/stderr when problems occur handling
        # logs from remote Tool Meisters.
        logger = logging.getLogger("tm_log_capture_thread")
        logger.setLevel(logging.WARNING)
        tm_log_file = self.benchmark_run_dir / "tm" / "tm.logs"
        with tm_log_file.open("w") as fp:
            try:
                for log_msg in self._to_logging_chan.fetch_message(logger):
                    fp.write(f"{log_msg}\n")
                    fp.flush()
            except redis.ConnectionError:
                # We don't bother reporting any connection errors.
                pass
            except ValueError as exc:
                # FIXME - Why do we need to do this?
                if exc.args[0] == "I/O operation on closed file.":
                    pass
                raise
            except Exception:
                self.logger.exception("Failed to capture logs from Redis server")

    def wait_for_initial_tms(self):
        """wait_for_initial_tms - Wait for the proper number of TMs to
        register, and when they are all registered, return a dictionary of the
        registered tool meister(s) with data and metadata.
        """
        expecting_tms = dict()
        for tm in self.tools.keys():
            expecting_tms[tm] = None
        assert (
            len(expecting_tms.keys()) > 0
        ), f"what? no tools registered? {self.tools.keys()}"
        tms = dict()
        for data in self._from_tms_chan.fetch_json(self.logger):
            # We expect the payload to look like:
            #   { "kind": "<ds|tm>",
            #     "hostname": "<hostname>",
            #     "pid": "<pid>",
            #     ...
            #   }
            # Where 'kind' is either 'ds' (data-sink) or 'tm' (tool-meister),
            # 'hostname' is the host name on which that entity is running, and
            # 'pid' is that entity's PID on that host. Each TM can add an
            # arbitrary set of other fields.
            try:
                kind = data["kind"]
                host = data["hostname"]
                pid = data["pid"]
            except KeyError:
                self.logger.warning("unrecognized data payload in message, %r", data)
                continue
            else:
                if kind != "tm":
                    self.logger.warning(
                        "unrecognized 'kind', in data payload, %r", data
                    )
                    continue
                if host in tms:
                    assert (
                        host not in expecting_tms
                    ), f"what? {host} unexpectedly in {expecting_tms.keys()}"
                    self.logger.warning(
                        "duplicate 'host' encountered in data payload, %r", data
                    )
                    continue
                if not pid:
                    self.logger.warning(
                        "empty 'pid' encountered in data payload, %r", data
                    )
                    continue
                try:
                    del expecting_tms[host]
                except KeyError:
                    self.logger.warning("unexpected TM reported in, %r", data)
                    continue
                else:
                    assert (
                        host in self.tools
                    ), f"what? {host} not in {self.tools.keys()}"
                    assert "tools" not in data, f"what? {data!r}"
                    data["tools"] = self.tools[host]
                    tms[host] = data
            if not expecting_tms:
                # All the expected Tool Meisters have reported back to us.
                break
        return tms

    def record_tms(self, tms):
        """record_tms - record the Tool Meister data and metadata returned from
        the startup acknowledgement messages collected in "tms".

        The first thing we have to do is setup self._tm_tracking properly,
        adding which tools are no-ops, transient, and persistent, and properly
        record the initial "posted" state.

        The second thing we do is record all the data and metadata about the
        Tool Meisters in the ${benchmark_run_dir}/metadata.log file.
        """
        persistent_tools_l = self.tool_metadata.getPersistentTools()
        transient_tools_l = self.tool_metadata.getTransientTools()
        for host, tm in tms.items():
            assert tm["kind"] == "tm", f"what? {tm!r}"
            assert "tools" in tm, f"what? {tm!r}"
            tools = tm["tools"]
            noop_tools = []
            persistent_tools = []
            transient_tools = []
            for tool_name in tools.keys():
                if tool_name in persistent_tools_l:
                    persistent_tools.append(tool_name)
                elif tool_name in BaseCollector.allowed_tools:
                    noop_tools.append(tool_name)
                elif tool_name in transient_tools_l:
                    transient_tools.append(tool_name)
                else:
                    self.logger.error(
                        f"Registered tool {tool_name} is not recognized in tool metadata"
                    )
            tm["noop_tools"] = noop_tools
            tm["persistent_tools"] = persistent_tools
            tm["transient_tools"] = transient_tools

            if tm["hostname"] == self.hostname:
                # The "localhost" Tool Meister instance does not send data
                # to the Tool Data Sink, it just writes it locally.
                tm["posted"] = None
            else:
                # The `posted` field is "dormant" to start (as set below),
                # "waiting" when we transition to the "send" state, "dormant"
                # when we receive data from the target Tool Meister host.
                tm["posted"] = "dormant"

        # Opportunistically capture the caller's SSH configuration in case
        # they have host specific configurations they might want to consider
        # in the future when reviewing historical data.  The host names used
        # in the config file might be very different from what tools capture
        # in their output.

        # cp -L  ${HOME}/.ssh/config   ${dir}/ssh.config > /dev/null 2>&1
        home = os.environ.get("HOME", "")
        if home:
            src = str(Path(home) / ".ssh" / "config")
            dst = str(self.benchmark_run_dir / "ssh.config")
            try:
                shutil.copyfile(src, dst)
            except FileNotFoundError:
                pass
            except Exception as exc:
                self.logger.warning("failed to copy %s to %s: %s", src, dst, exc)
        # cp -L  /etc/ssh/ssh_config   ${dir}/ > /dev/null 2>&1
        etc_ssh = Path("/etc") / "ssh"
        src = str(etc_ssh / "ssh_config")
        dst = str(self.benchmark_run_dir / "ssh_config")
        try:
            shutil.copyfile(src, dst)
        except FileNotFoundError:
            pass
        except Exception as exc:
            self.logger.warning("failed to copy %s to %s: %s", src, dst, exc)
        #
        # Okay, this is where Python 3 falls down: replacing command line
        # utilities available via `bash` with Python 3 modules.
        #
        # Turns out you can't use `shutil.copytree()` inside a container to
        # replace `cp -RL`.
        #
        # That code attempts to use `os.setxattr()` at the lowest level to
        # copy all the attributes properly.  But when not running as a real
        # `root` user in a container, you can't copy all attributes, and a
        # "Permission denied" exception is raised.
        #
        # Arguably this is a bug in shutil.copytree(); cp doesn't copy xattr
        # unless --preserve and even so, --preserve --no-preserve=xattr would
        # allow a workaround; but Python's package doesn't provide equivalents
        # except to override the default use shutil.copy2 with shutil.copy and
        # that doesn't affect how shutil.copyfile() updates directory
        # attributes.
        #
        #
        # The original `pbench-metadata-log` code just used `cp -rL` and it
        # worked both in and out of a container.  So we just invoke that
        # command directly.
        #
        # cp -rL /etc/ssh/ssh_config.d ${dir}/ > /dev/null 2>&1
        subprocess.run(
            [cp_path, "-rL", "/etc/ssh/ssh_config.d", f"{self.benchmark_run_dir}/"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        mdlog_name = self.benchmark_run_dir / "metadata.log"
        mdlog = ConfigParser()
        try:
            with mdlog_name.open("r") as fp:
                mdlog.read_file(fp)
        except FileNotFoundError:
            # Ignore if it doesn't exist
            pass

        section = "pbench"
        mdlog.add_section(section)
        # Users have a funny way of adding '%' characters to the config
        # variable, so we have to be sure we handle "%" characters in the
        # config metadata properly.
        mdlog.set(section, "config", self.optional_md["config"].replace("%", "%%"))
        mdlog.set(section, "date", self.optional_md["date"])
        # Users have a funny way of adding '%' characters to the run
        # directory, so we have to be sure we handle "%" characters in the
        # directory name metadata properly.
        mdlog.set(section, "name", self.benchmark_run_dir.name.replace("%", "%%"))
        version, seqno, sha1, hostdata = collect_local_info(self.pbench_bin)
        rpm_version = f"v{version}-{seqno}g{sha1}"
        mdlog.set(section, "rpm-version", rpm_version)
        rpm_versions = dict()
        rpm_versions[rpm_version] = 1
        mdlog.set(section, "script", self.optional_md["script"])

        section = "controller"
        mdlog.add_section(section)
        mdlog.set(section, "hostname", self.hostname)
        mdlog.set(section, "hostname-s", hostdata["s"])
        mdlog.set(section, "hostname-f", hostdata["f"])
        mdlog.set(section, "hostname-i", hostdata["i"])
        mdlog.set(section, "hostname-A", hostdata["A"])
        mdlog.set(section, "hostname-I", hostdata["I"])
        mdlog.set(section, "ssh_opts", self.optional_md["ssh_opts"])

        section = "run"
        mdlog.add_section(section)
        mdlog.set(section, "controller", self.hostname)
        mdlog.set(section, "start_run", _now("start"))

        section = "tools"
        mdlog.add_section(section)
        mdlog.set(section, "hosts", " ".join(sorted(list(self.tools.keys()))))
        mdlog.set(section, "group", self.tool_group)
        mdlog.set(section, "trigger", str(self.tool_trigger))

        for host, tm in sorted(tms.items()):
            section = f"tools/{host}"
            mdlog.add_section(section)
            mdlog.set(section, "label", tm["label"])
            tools_string = ",".join(sorted(list(tm["tools"].keys())))
            mdlog.set(section, "tools", tools_string)

            # add host data
            mdlog.set(section, "hostname-s", tm["hostname_s"])
            mdlog.set(section, "hostname-f", tm["hostname_f"])
            mdlog.set(section, "hostname-i", tm["hostname_i"])
            mdlog.set(section, "hostname-A", tm["hostname_A"])
            mdlog.set(section, "hostname-I", tm["hostname_I"])
            ver, seq, sha = tm["version"], tm["seqno"], tm["sha1"]
            rpm_version = f"v{ver}-{seq}g{sha}"
            try:
                rpm_versions[rpm_version] += 1
            except KeyError:
                rpm_versions[rpm_version] = 1
            mdlog.set(section, "rpm-version", rpm_version)

            for tool, opts in tm["tools"].items():
                # Compatibility - keep each tool with options listed
                mdlog.set(section, tool, opts)

                # New way is to give each tool a separate section storing the
                # options and install results individually.
                new_section = f"tools/{host}/{tool}"
                mdlog.add_section(new_section)
                mdlog.set(new_section, "options", opts)
                try:
                    code, msg = tm["installs"][tool]
                except KeyError:
                    pass
                else:
                    mdlog.set(new_section, "install_check_status_code", str(code))
                    mdlog.set(new_section, "install_check_output", msg)

        # Review how many different RPM versions we have accumulated.
        rpm_versions_cnt = len(rpm_versions.keys())
        if rpm_versions_cnt > 1:
            self.logger.warning(
                "Tool Meisters do not share the same RPM versions: %r", rpm_versions
            )
            section = "run"
            mdlog.set(
                section, "tool_meister_version_mismatch_count", f"{rpm_versions_cnt}"
            )

        with (mdlog_name).open("w") as fp:
            mdlog.write(fp)

        return tms

    def _valid_data(self, data):
        try:
            action = data["action"]
            group = data["group"]
            directory = data["directory"]
            args = data["args"]
        except KeyError:
            self.logger.warning("unrecognized data payload in message, %r", data)
            return None
        else:
            if action not in tm_allowed_actions:
                self.logger.warning("unrecognized action in message, %r", data)
                return None
            elif group != self.tool_group:
                self.logger.warning("unrecognized tool group in message, %r", data)
                return None
            else:
                return (action, directory, args)

    def execute(self):
        """execute - Driver for listening to client requests and taking action on
        them.
        """
        try:
            # At this point, all the Tool Meisters started by the external
            # orchestrator will publish a message on the "<prefix>-from-tms"
            # channel indicating they have started, including additional
            # metadata about their operation.  We need to wait for the TMs to
            # all report in now.
            tms = self.wait_for_initial_tms()

            # Record the collected information about the Tool Meisters in the
            # run directory.
            self._tm_tracking = self.record_tms(tms)
            self._num_tms = len(self._tm_tracking.keys())

            # Tell the entity that started us who we are, indicating we're
            # ready, and all the TMs are ready.
            started_msg = dict(kind="ds", action="startup", status="success")
            self.logger.debug("publish %s", self._to_client_channel)
            num_present = self.redis_server.publish(
                self._to_client_channel, json.dumps(started_msg, sort_keys=True)
            )
            if num_present == 0:
                raise Exception("Tool Data Sink started by nobody is listening")
            self.logger.debug("published %s", self._to_client_channel)

            for data in self._from_client_chan.fetch_json(self.logger):
                ret_val = self._valid_data(data)
                if ret_val is None:
                    continue
                action, directory, args = ret_val[0], ret_val[1], ret_val[2]
                self.execute_action(action, directory, args, data)
            self.logger.info("Tool Data Sink terminating")
        except redis.ConnectionError:
            self.logger.warning(
                "run closing down after losing connection to redis server"
            )
        except Exception:
            self.logger.exception("execute exception")
        finally:
            self._to_logging_chan.unsubscribe()

    def _wait_for_all_data(self):
        """wait_for_all_data - block the caller until all of the registered
        tool meisters have sent their data.

        Waiting is a no-op for all actions except the "data actions" (see
        self._data_actions).  For a "data" action, we are expecting to hear from
        all registered tool meisters.
        """
        assert (
            self.action in self._data_actions
        ), f"expected action to be one of {self._data_actions!r}, not {self.action!r}"
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

    def _change_tm_tracking(self, action, curr, new):
        """_change_tm_tracking - update the posted action from the current
        expected value to the target new value in the tracking dictionary.

        Assumes self._lock is already acquired by our caller.
        """
        assert self._tm_tracking is not None, "Logic bomb!  self._tm_tracking is None"
        for hostname, tm in self._tm_tracking.items():
            if tm["posted"] is None:
                continue
            if action == "send" and not tm["transient_tools"]:
                # Ignore any Tool Meisters who do not have any transient
                # tools.
                continue
            assert (
                tm["posted"] == curr
            ), f"_change_tm_tracking unexpected tm posted value, {tm!r}"
            tm["posted"] = new

    def _forward_tms(self, data):
        """_forward_tms - forward the action data payload to the known Tool
        Meisters.

        Log messages will be posted if any errors were encountered.

        Return 0 on success, non-zero to indicate an error.
        """
        self.logger.debug("publish %s", self._to_tms_channel)
        try:
            num_present = self.redis_server.publish(
                self._to_tms_channel, json.dumps(data, sort_keys=True)
            )
        except Exception:
            self.logger.exception("Failed to publish action message to TMs")
            ret_val = 1
        else:
            self.logger.debug("published %s", self._to_tms_channel)
            if num_present != self._num_tms:
                self.logger.error(
                    "TM action message received by %d subscribers", num_present
                )
                ret_val = 1
            else:
                self.logger.debug("posted TM action message, %r", data)
                ret_val = 0
        return ret_val

    def _wait_for_tms(self):
        """_wait_for_tms - Wait for all the Tool Meisters to report back the
        status of their action.

        Returns 0 on success, non-zero to indicate an error.
        """
        # Wait for all Tool Meisters to report back their operational status.
        ret_val = 0
        done_count = 0
        for data in self._from_tms_chan.fetch_json(self.logger):
            try:
                kind = data["kind"]
                status = data["status"]
            except Exception:
                self.logger.error("unrecognized status payload, %r", data)
                ret_val = 1
            else:
                if kind != "tm":
                    self.logger.warning("unrecognized kind in payload, %r", data)
                    ret_val = 1
                elif status not in ("success", "terminated"):
                    self.logger.warning(
                        "Status message not successful: '%s'", status,
                    )
                    ret_val = 1
                done_count += 1
            if done_count >= self._num_tms:
                break
        return ret_val

    def _forward_tms_and_wait(self, data):
        """_forward_tms_and_wait - simple wrapper to perform the typical steps
        of forwarding the action payload to the Tool Meisters and then waiting
        for their response.

        Returns the return value of either _forward_tms() or _wait_for_tms().
        """
        ret_val = self._forward_tms(data)
        if ret_val == 0:
            ret_val = self._wait_for_tms()
        return ret_val

    def execute_action(self, action, directory_str, args, data):
        """execute_action - given an action, directory string, arguments, and
        a data dictionary, execute the sequence of steps required for that
        action.

        The "watcher" thread has already validated the action field, we then
        validate the directory field.

        Public method, returns None, raises no exceptions explicitly, called
        by the "watcher" thread.
        """
        if action == "terminate":
            # Recording the ending time first thing to avoid as much skew as
            # possible.
            now = _now("end")
            # Forward terminate message to all TMs and wait for their
            # acknowledgement.
            self._forward_tms_and_wait(data)
            # Record the final information in the metadata.log file for the
            # "end of a run" ("run/end_run") and the contents of the
            # ".iterations" file, if it exists.  This includes recording when
            # the caller wants to report that it is stopping all the Tool
            # Meisters due to an interruption (SIGINT or otherwise).
            #
            mdlog_name = self.benchmark_run_dir / "metadata.log"
            mdlog = ConfigParser()
            try:
                with (mdlog_name).open("r") as fp:
                    mdlog.read_file(fp)
            except FileNotFoundError:
                # Ignore if it doesn't exist
                self.logger.info("Missing meta-data log file: %s", mdlog_name)
            else:
                section = "run"
                try:
                    mdlog.add_section(section)
                except DuplicateSectionError:
                    pass
                # timestamp   ==> run / end_run
                mdlog.set(section, "end_run", now)
                if args["interrupt"]:
                    # args["interrupt"] == True ==> run / run_interrupted
                    mdlog.set(section, "run_interrupted", "true")
                iterations = self.benchmark_run_dir / ".iterations"
                try:
                    iterations_val = iterations.read_text()
                except FileNotFoundError:
                    # Ignore a missing .iterations file.
                    pass
                else:
                    # .iterations ==> pbench / iterations
                    section = "pbench"
                    try:
                        mdlog.add_section(section)
                    except DuplicateSectionError:
                        pass
                    iterations_l = iterations_val.strip().split()
                    iterations_str = ", ".join(iterations_l)
                    mdlog.set(section, "iterations", iterations_str)
                # Write out the final meta data contents.
                with (mdlog_name).open("w") as fp:
                    mdlog.write(fp)

            self._from_client_chan.close()
            self._from_tms_chan.close()
            self._to_logging_chan.unsubscribe()
            return

        directory = Path(directory_str)
        if not directory.is_dir():
            self.logger.error(
                "action '%s' with non-existent directory, '%s'", action, directory,
            )
            self._send_client_status(action, "invalid directory")
            return
        try:
            # Check that "directory" has a prefix of self.benchmark_run_dir
            directory.relative_to(self.benchmark_run_dir)
        except ValueError:
            self.logger.error(
                "action '%s' with invalid directory,"
                " '%s' (not a sub-directory of '%s')",
                action,
                directory,
                self.benchmark_run_dir,
            )
            self._send_client_status(action, "directory not a prefix of run directory")
            return

        with self._lock:
            # Handle all actions underneath the lock for consistency.
            self.action = action
            if action == "init":
                # To be safe, clear the data context to catch bad PUTs
                self.data_ctx = None
                # Forward to TMs
                ret_val = self._forward_tms_and_wait(data)
                # Start all the persistent tool collectors locally.
                prom_tool_dict = {}
                pcp_tool_dict = {}
                for tm in self._tm_tracking:
                    prom_tools = []
                    pcp_tools = []
                    persist_tools = self._tm_tracking[tm]["persistent_tools"]
                    for tool in persist_tools:
                        tool_data = self.tool_metadata.getProperties(tool)
                        if tool_data["collector"] == "prometheus":
                            prom_tools.append(tool)
                        elif tool_data["collector"] == "pcp":
                            if self._tm_tracking[tm]["transient_tools"]:
                                pcp_tools = self._tm_tracking[tm]["transient_tools"]
                            else:
                                pcp_tools = ["base_pcp"]
                    if len(prom_tools) > 0:
                        prom_tool_dict[self._tm_tracking[tm]["hostname"]] = prom_tools
                    if len(pcp_tools) > 0:
                        pcp_tool_dict[self._tm_tracking[tm]["hostname"]] = pcp_tools
                if prom_tool_dict or pcp_tool_dict:
                    tool_names = list(prom_tool_dict.keys())
                    tool_names.extend(list(pcp_tool_dict.keys()))
                    self.logger.debug(
                        "init persistent tools on tool meisters: %s",
                        ", ".join(tool_names),
                    )
                else:
                    self.logger.debug("No persistent tools to init")
                if prom_tool_dict:
                    self._prom_server = PromCollector(
                        self.pbench_bin,
                        self.benchmark_run_dir,
                        self.tool_group,
                        prom_tool_dict,
                        self.tool_metadata,
                        self.logger,
                    )
                    self._prom_server.launch()
                if pcp_tool_dict:
                    self._pcp_server = PCPCollector(
                        self.pbench_bin,
                        self.benchmark_run_dir,
                        self.tool_group,
                        pcp_tool_dict,
                        self.tool_metadata,
                        self.logger,
                    )
                    self._pcp_server.launch()
            elif action == "end":
                # To be safe, clear the data context to catch bad PUTs
                self.data_ctx = None
                # Forward to TMs
                ret_val = self._forward_tms_and_wait(data)
                # Now we can shutdown local persistent tool collectors.
                if self._prom_server:
                    self._prom_server.terminate()
                if self._pcp_server:
                    self._pcp_server.terminate()
            elif action in self._data_actions:
                # The remote Tool Meisters will be hashing the directory
                # argument this way when invoking the PUT method.  They just
                # consider the directory argument to be an opaque context.
                # The Tool Data Sink, writes the data it receives to that
                # directory, but expect them to provide the opaque context in
                # the URL for the PUT method.
                directory_bytes = directory_str.encode("utf-8")
                self.data_ctx = hashlib.md5(directory_bytes).hexdigest()
                self.directory = Path(directory_str)

                # Forward to TMs
                ret_val = self._forward_tms(data)
                if ret_val == 0:
                    # Wait for all data
                    self._change_tm_tracking(action, "dormant", "waiting")
                    self._wait_for_all_data()
                    # At this point all tracking data should be "dormant" again.
                    ret_val = self._wait_for_tms()

                # To be safe, clear the data context and directory to catch
                # bad PUTs
                self.data_ctx = None
                self.directory = None
            else:
                assert action in ("start", "stop",), f"Unexpected action, '{action}'"
                # Forward to TMs
                ret_val = self._forward_tms_and_wait(data)
            self.action = None

        msg = "success" if ret_val == 0 else "failure communicating with TMs"
        self._send_client_status(action, msg)

    def _send_client_status(self, action, status):
        """_send_client_status - encapsulate sending back the status message to
        the client.

        Returns 0 on success, 1 on failure, logging any exceptions encountered.
        """
        # The published client status message contains three pieces of
        # information:
        #   {
        #     "kind": "ds",
        #     "action": "< name of action taken >",
        #     "status": "success|< a message to be displayed on error >"
        #   }
        msg = dict(kind="ds", action=action, status=status)
        self.logger.debug("publish %s", self._to_client_channel)
        try:
            num_present = self.redis_server.publish(
                self._to_client_channel, json.dumps(msg, sort_keys=True)
            )
        except Exception:
            self.logger.exception("Failed to publish client status message")
            ret_val = 1
        else:
            self.logger.debug("published %s", self._to_client_channel)
            if num_present != 1:
                self.logger.error(
                    "client status message received by %d subscribers", num_present
                )
                ret_val = 1
            else:
                self.logger.debug("posted client status, %r", status)
                ret_val = 0
        return ret_val

    def put_document(self, data_ctx, hostname):
        """put_document - PUT callback method for Bottle web server end point

        The put_document method is called by threads serving web requests.
        There can be N threads configured at one time calling this method.

        Public method, returns None, raises no exceptions directly, calls the
        Bottle abort() method for error handling.

        """
        try:
            with self._lock:
                if self.action not in self._data_actions:
                    abort(400, f"Can't accept PUT requests in action '{self.action}'")
                if self.data_ctx != data_ctx:
                    # Tool Data Sink and this Tool Meister are out of sync as to
                    # what data is expected.
                    abort(400, f"Unexpected data context, '{data_ctx}'")
                if self.directory is None:
                    self.logger.error("ERROR - no directory to store documents")
                    abort(500, "INTERNAL ERROR")
                # Fetch the Tool Meister tracking record for this host and verify
                # it is in the expected waiting state.
                try:
                    tm_tracker = self._tm_tracking[hostname]
                except KeyError:
                    abort(400, f"Unknown Tool Meister '{hostname}'")
                else:
                    if tm_tracker["posted"] != "waiting":
                        self.logger.error(
                            "INTERNAL ERROR: expected Tool Meister for host, '%s', in"
                            " `waiting` state, found in `%s` state",
                            hostname,
                            tm_tracker["posted"],
                        )
                        abort(400, "No data expected from a Tool Meister")
                    elif self.action == "send":
                        # Only Tool Meisters with at least one transient tool
                        # will send data to the Tool Data Sink, so return an
                        # error to those Tool Meisters that issued "send" but
                        # do not have any transient tools.
                        if not tm_tracker["transient_tools"]:
                            abort(400, "Not expecting tool data from Tool Meister")

            try:
                content_length = int(request["CONTENT_LENGTH"])
            except ValueError:
                abort(400, "Invalid content-length header, not an integer")
            except Exception:
                abort(400, "Missing required content-length header")
            else:
                if content_length > _MAX_TOOL_DATA_SIZE:
                    abort(400, "Content object too large")
                remaining_bytes = content_length

            try:
                exp_md5 = request["HTTP_MD5SUM"]
            except Exception:
                self.logger.exception(request.keys())
                abort(400, "Missing required md5sum header")

            target_dir = self.directory
            if not target_dir.is_dir():
                self.logger.error("ERROR - directory, '%s', does not exist", target_dir)
                abort(500, "INTERNAL ERROR")
            host_data_tb_name = target_dir / f"{hostname}.tar.xz"
            if host_data_tb_name.exists():
                abort(409, f"{host_data_tb_name} already uploaded")
            host_data_tb_md5 = Path(f"{host_data_tb_name}.md5")

            with tempfile.NamedTemporaryFile(mode="wb", dir=target_dir) as ofp:
                total_bytes = 0
                iostr = request["wsgi.input"]
                h = hashlib.md5()
                while remaining_bytes > 0:
                    buf = iostr.read(
                        _BUFFER_SIZE
                        if remaining_bytes > _BUFFER_SIZE
                        else remaining_bytes
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
                    with host_data_tb_md5.open("w") as md5fp:
                        md5fp.write(f"{exp_md5} {host_data_tb_name.name}\n")
                except Exception:
                    try:
                        os.remove(host_data_tb_md5)
                    except Exception as exc:
                        self.logger.warning(
                            "Failed to remove .md5 %s when trying to clean up: %s",
                            host_data_tb_md5,
                            exc,
                        )
                    self.logger.exception(
                        "Failed to write .md5 file, '%s'", host_data_tb_md5
                    )
                    raise

                # Then create the final filename link to the temporary file.
                try:
                    os.link(ofp.name, host_data_tb_name)
                except Exception:
                    try:
                        os.remove(host_data_tb_md5)
                    except Exception as exc:
                        self.logger.warning(
                            "Failed to remove .md5 %s when trying to clean up: %s",
                            host_data_tb_md5,
                            exc,
                        )
                    self.logger.exception(
                        "Failed to rename tar ball '%s' to '%s'",
                        ofp.name,
                        host_data_tb_md5,
                    )
                    raise
                else:
                    self.logger.debug(
                        "Successfully wrote %s (%s.md5)",
                        host_data_tb_name,
                        host_data_tb_name,
                    )

            # Now unpack that tar ball
            o_file = target_dir / f"{hostname}.tar.out"
            e_file = target_dir / f"{hostname}.tar.err"
            try:
                # Invoke tar directly for efficiency.
                with o_file.open("w") as ofp, e_file.open("w") as efp:
                    cp = subprocess.run(
                        [tar_path, "-xf", host_data_tb_name],
                        cwd=target_dir,
                        stdin=None,
                        stdout=ofp,
                        stderr=efp,
                    )
            except Exception:
                self.logger.exception(
                    "Failed to extract tar ball, '%s'", host_data_tb_name
                )
                abort(500, "INTERNAL ERROR")
            else:
                if cp.returncode != 0:
                    self.logger.error(
                        "Failed to create tar ball; return code: %d", cp.returncode
                    )
                    abort(500, "INTERNAL ERROR")
                else:
                    self.logger.debug("Successfully unpacked %s", host_data_tb_name)
                    try:
                        o_file.unlink()
                        e_file.unlink()
                        host_data_tb_md5.unlink()
                        host_data_tb_name.unlink()
                    except Exception:
                        self.logger.exception(
                            "Error removing unpacked tar ball '%s' and it's .md5",
                            host_data_tb_name,
                        )

            # Tell the waiting "watcher" thread that another PUT document has
            # arrived.
            with self._lock:
                tm_tracker = self._tm_tracking[hostname]
                assert tm_tracker["posted"] == "waiting", f"tm_tracker = {tm_tracker!r}"
                tm_tracker["posted"] = "dormant"
                self._cv.notify()
        except Exception:
            self.logger.exception("Uncaught error")
            abort(500, "INTERNAL ERROR")


def main(argv):
    _prog = Path(argv[0])
    PROG = _prog.name
    pbench_bin = _prog.parent.parent

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

    global cp_path
    cp_path = find_executable("cp")
    if cp_path is None:
        logger.error("External 'cp' executable not found")
        return 2

    global podman_path
    podman_path = find_executable("podman")
    if podman_path is None:
        logger.error("External 'podman' executable not found")
        return 2

    try:
        redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)
    except Exception as e:
        logger.error(
            "Unable to connect to redis server, %s:%s: %s", redis_host, redis_port, e
        )
        return 4

    try:
        hostname = os.environ["_pbench_full_hostname"]
    except KeyError:
        logger.error("Unable to fetch _pbench_full_hostname environment variable")
        return 4

    try:
        params_raw = redis_server.get(param_key)
        if params_raw is None:
            logger.error('Parameter key, "%s" does not exist.', param_key)
            return 5
        logger.debug("params_key (%s): %r", param_key, params_raw)
        params_str = params_raw.decode("utf-8")
        # The expected parameters for this "data-sink" is what "channel" to
        # subscribe to for the tool meister operational life-cycle.  The
        # data-sink listens for the actions, sysinfo | init | start | stop |
        # send | end | terminate, exiting when "terminate" is received,
        # marking the state in which data is captured.
        #
        # E.g. params = '{ "channel_prefix": "some-prefix",
        #                  "benchmark_run_dir": "/loo/goo" }'
        params = json.loads(params_str)
        channel_prefix = params["channel_prefix"]
        benchmark_run_dir = Path(params["benchmark_run_dir"]).resolve(strict=True)
        bind_hostname = params["bind_hostname"]
        tool_group = params["group"]
        tool_trigger = params["tool_trigger"]
        tools = params["tools"]
        tool_metadata = ToolMetadata.tool_md_from_dict(params["tool_metadata"])
    except Exception as ex:
        logger.error("Unable to fetch and decode parameter key, %s: %s", param_key, ex)
        return 6
    else:
        if not benchmark_run_dir.is_dir():
            logger.error(
                "Run directory argument, %s, must be a real directory.",
                benchmark_run_dir,
            )
            return 7
        logger.debug("Tool Data Sink parameters check out, daemonizing ...")
        redis_server.connection_pool.disconnect()
        del redis_server

    optional_md = params["optional_md"]

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
                return 8
            else:
                logger.debug("constructed Redis() object")

            with ToolDataSink(
                pbench_bin,
                hostname,
                bind_hostname,
                redis_server,
                channel_prefix,
                benchmark_run_dir,
                tool_group,
                tool_trigger,
                tools,
                tool_metadata,
                optional_md,
                logger,
            ) as tds_app:
                tds_app.execute()
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                logger.error(
                    "ERROR - tool data sink failed to start, %s:%s already in use",
                    bind_hostname,
                    tds_port,
                )
            else:
                logger.exception("ERROR - failed to start the tool data sink")
        except Exception:
            logger.exception("ERROR - failed to start the tool data sink")

    return 0
