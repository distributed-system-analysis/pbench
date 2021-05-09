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
import subprocess
import sys
import tempfile

from configparser import ConfigParser, DuplicateSectionError
from datetime import datetime
from distutils.spawn import find_executable
from http import HTTPStatus
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from threading import Thread, Lock, Condition
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pidfile
import redis

from bottle import Bottle, ServerAdapter, request, abort
from daemon import DaemonContext

from pbench.agent.constants import (
    tm_allowed_actions,
    tm_channel_suffix_from_client,
    tm_channel_suffix_from_tms,
    tm_channel_suffix_to_client,
    tm_channel_suffix_to_logging,
    tm_channel_suffix_to_tms,
)
from pbench.agent.redis import RedisChannelSubscriber, wait_for_conn_and_key
from pbench.agent.toolmetadata import ToolMetadata
from pbench.agent.utils import collect_local_info


# Logging format string for unit tests
fmtstr_ut = "%(levelname)s %(name)s %(funcName)s -- %(message)s"
fmtstr = "%(asctime)s %(levelname)s %(process)s %(thread)s %(name)s %(funcName)s %(lineno)d -- %(message)s"


# Read in 64 KB chunks off the wire for HTTP PUT requests.
_BUFFER_SIZE = 65536

# Maximum size of the tar ball for collected tool data.
_MAX_TOOL_DATA_SIZE = 2 ** 30


def _now(when):
    """_now - An ugly hack to facilitate testing without the ability to mock.

    Instead of directly calling `datetime.utcnow().isoformat()`, each call
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
    """DataSinkWsgiServer - a re-implementation of Bottle's WSGIRefServer
    where we have access to the underlying WSGIServer instance in order to
    invoke its stop() method, and we also provide an WSGIRequestHandler with
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
        self._err_code = None
        self._err_text = None
        self._lock = Lock()
        self._cv = Condition(lock=self._lock)
        self._logger = logger

    def _do_notify(self, text=None, code=0, server=None):
        """_do_notify - simple helper method to encapsulate method of notification.
        """
        with self._lock:
            self._err_text = text
            self._err_code = code
            self._server = server
            self._cv.notify()

    def run(self, app):
        """run - Start the WSGI server, called by the Bottle framework.

        Intended to be run as a separate thread.

        We record the outcome of the `make_server` call for success or failure
        and notify anybody waiting for this thread to succeed.
        """
        assert self._server is None, "'run' method called twice"
        self._logger.debug("Making tool data sink WSGI server ...")
        try:
            server = make_server(self.host, self.port, app, **self.options)
        except OSError as exc:
            assert exc.errno != 0, "Logic bomb!  OSError exception with no errno value"
            self._do_notify(str(exc), exc.errno)
            raise
        except Exception as exc:
            self._logger.exception("Unexpected error in WSGI server")
            self._do_notify(str(exc), -1)
            raise
        else:
            self._logger.debug("Successfully created WSGI server")
            self._do_notify(server=server)
            self._logger.debug("Running tool data sink WSGI server ...")
            server.serve_forever()

    def wait(self):
        """ wait - wait for the WSGI thread executing the `run` method to start
        running and successfully create a WSGI server object, or fail trying.

        Returns a tuple of the error text and the error code set by the _run()
        method attempting to create the WSGI server.  The error code will be
        0 on success, an Errno value, or -1 if an expected exception was
        raised.
        """
        with self._lock:
            while self._err_code is None:
                self._cv.wait()
        return self._err_text, self._err_code

    def stop(self):
        """ stop - stop the running WSGI server via the shutdown() method of
        the WSGI server object.
        """
        # We have to wait for the thread to start the server and fill in the
        # server object first.
        self.wait()
        if self._err_code == 0:
            self._server.shutdown()


class ToolDataSinkError(Exception):
    """ToolDataSinkError - generic exception class for Tool Data Sink related
    exceptions.
    """

    pass


class BaseCollector:
    """Abstract class for persistent tool data collectors"""

    # Each sub-class must provide a name.
    name = None
    allowed_tools = {"noop-collector": None}

    def __init__(
        self,
        pbench_bin,
        benchmark_run_dir,
        tool_group,
        host_tools_dict,
        tool_metadata,
        tar_path,
        logger,
    ):
        """Constructor - responsible for recording the arguments, and creating
        the Environment() for template rendering.
        """
        self.templates_path = pbench_bin / "templates"
        assert (
            self.templates_path.is_dir()
        ), f"Logic bomb! {self.templates_path} does not exist as a directory"
        self.benchmark_run_dir = benchmark_run_dir
        self.tool_group = tool_group
        self.host_tools_dict = host_tools_dict
        self.tool_metadata = tool_metadata
        self.tar_path = tar_path
        self.logger = logger

        self.run = []
        self.tool_group_dir = self.benchmark_run_dir.local / f"tools-{self.tool_group}"
        self.tool_dir = self.tool_group_dir / self.name
        self.template_dir = Environment(
            autoescape=False,
            loader=FileSystemLoader(str(self.templates_path)),
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def launch(self):
        """launch - Abstract method for launching a persistent tool data
        collector.

        Must be overriden by the sub-class.
        """
        assert False, "Must be overriden by sub-class"

    def _mk_tool_dir(self):
        """_mk_tool_dir - create the tool directory for a persistent tool.

        Returns a Pathlib object of the created directory on success, None on
        failure.
        """
        try:
            self.tool_dir.mkdir()
        except Exception as exc:
            self.logger.error(
                "Tool directory %s creation failed: '%s'", self.tool_dir, exc
            )
            raise
        else:
            self.logger.debug("Create tool directory %s", self.tool_dir)

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
        errors = 0
        for run in self.run:
            try:
                run.terminate()
            except Exception as exc:
                self.logger.error(
                    "Failed to terminate expected collector process: '%s'", exc
                )
                errors += 1
        for run in self.run:
            try:
                sts = run.wait()
            except Exception as exc:
                self.logger.error(
                    "Failed to terminate expected collector process: '%s'", exc
                )
                errors += 1
            else:
                if sts != 0:
                    self.logger.warning("Collector process terminated with %d", sts)
        if errors > 0:
            raise ToolDataSinkError("Failed to terminate all the collector processes")


class PromCollector(BaseCollector):
    """Persistent tool data collector for tools compatible with Prometheus"""

    name = "prometheus"

    def __init__(self, *args, **kwargs):
        """Constructor - responsible for setting up the particulars for the
        Prometheus collector, including how to instruct prometheus to gather
        tool data.
        """
        self.prometheus_path = find_executable("prometheus")
        if self.prometheus_path is None:
            raise ToolDataSinkError("External 'prometheus' executable not found")

        super().__init__(*args, **kwargs)
        self.tool_context = []
        for host, tools in sorted(self.host_tools_dict.items()):
            for tool in sorted(tools["names"]):
                port = self.tool_metadata.getProperties(tool)["port"]
                self.tool_context.append(
                    dict(hostname=f"{host}_{tool}", hostport=f"{host}:{port}")
                )
        if not self.tool_context:
            raise ToolDataSinkError(
                "Expected prometheus persistent tool context not found"
            )

    def launch(self):
        """launch - creates the YAML file that directs Prometheus's behavior,
        the directory prometheus will write its data, and creates the sub-
        process that runs Prometheus.
        """
        try:
            self._mk_tool_dir()
        except Exception:
            return

        yml = self.render_from_template("prometheus.yml", dict(tools=self.tool_context))
        assert yml is not None, f"Logic bomb!  {self.tool_context!r}"
        with (self.tool_dir / "prometheus.yml").open("w") as config:
            config.write(yml)

        args = [
            self.prometheus_path,
            f"--config.file={self.tool_dir}/prometheus.yml",
            f"--storage.tsdb.path={self.tool_dir}",
            "--web.console.libraries=/usr/share/prometheus/console_libraries",
            "--web.console.templates=/usr/share/prometheus/consoles",
        ]
        with (self.tool_dir / "prom.log").open("w") as prom_logs:
            try:
                run = subprocess.Popen(
                    args, cwd=self.tool_dir, stdout=prom_logs, stderr=prom_logs
                )
            except Exception as exc:
                self.logger.error(
                    "Prometheus process creation failed: '%s', %r", exc, args
                )
                return
            else:
                self.run.append(run)

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
            self.tar_path,
            "--remove-files",
            "-Jcf",
            f"{self.tool_group_dir}/prometheus_data.tar.xz",
            "-C",
            f"{self.tool_group_dir}/",
            "prometheus",
        ]
        cp = subprocess.run(args)
        if cp.returncode != 0:
            self.logger.warning("Failed to tar up prometheus data: %r", args)


class PcpCollector(BaseCollector):
    """Persistent tool data collector for tools compatible with Prometheus"""

    name = "pcp"

    # Default path to the "pmlogger" executable.
    _pmcd_wait_path_def = "/usr/libexec/pcp/bin/pmcd_wait"
    _pmlogger_path_def = "/usr/bin/pmlogger"
    _pmproxy_path_def = "/usr/libexec/pcp/bin/pmproxy"

    def __init__(self, *args, redis_host=None, redis_port=None, **kwargs):
        """Constructor - responsible for setting up the state needed to run
        the PCP collector.
        """
        super().__init__(*args, **kwargs)
        self.redis_host = redis_host
        self.redis_port = redis_port
        pmcd_wait_path = find_executable("pmcd_wait")
        if pmcd_wait_path is None:
            pmcd_wait_path = self._pmcd_wait_path_def
        self.pmcd_wait_path = pmcd_wait_path
        pmlogger_path = find_executable("pmlogger")
        if pmlogger_path is None:
            pmlogger_path = self._pmlogger_path_def
        self.pmlogger_path = pmlogger_path
        pmproxy_path = find_executable("pmproxy")
        if pmproxy_path is None:
            pmproxy_path = self._pmproxy_path_def
        self.pmproxy_path = pmproxy_path

    def launch(self):
        """launch - responsible for creating the configuration file for
        collecting data from the register hosts, creates the directory for
        storing the collected data, and runs the PCP collector itself.
        """
        try:
            self._mk_tool_dir()
        except Exception:
            return
        data_dir = self.tool_dir / "data"
        try:
            data_dir.mkdir()
        except Exception as exc:
            self.logger.error(
                "PCP data directory %s creation failed: '%s'", data_dir, exc
            )
            return

        # Create all the host directories for the PCP data and create all the
        # processes which will wait for the pmcd processes to show up.
        pmcd_wait_l = []
        errors = 0
        for host in self.host_tools_dict:
            label = self.host_tools_dict[host]["label"]
            if label:
                label = f"{label}:"
            host_dir = data_dir / f"{label}{host}"
            log_dir = self.tool_dir / host
            try:
                log_dir.mkdir()
            except Exception as exc:
                self.logger.error(
                    "Log directory %s creation failed: '%s'", log_dir, exc
                )
                errors += 1
                continue
            try:
                host_dir.mkdir()
            except Exception as exc:
                self.logger.error(
                    "Host directory %s creation failed: '%s'", host_dir, exc
                )
                errors += 1
                continue

            args = [
                self.pmcd_wait_path,
                f"--host={host}:55677",
                "-t 30",
            ]
            self.logger.debug("Starting pmcd_wait, cwd %s, args %r", log_dir, args)
            with (log_dir / "pmlogger-proc.log").open("w") as pmlogger_logs:
                try:
                    run = subprocess.Popen(
                        args,
                        cwd=log_dir,
                        stdout=pmlogger_logs,
                        stderr=subprocess.STDOUT,
                    )
                except Exception as exc:
                    self.logger.error("Pmcd_wait process failed: '%s', %r", exc, args)
                    errors += 1
                else:
                    pmcd_wait_l.append((host, run))

        for host, pmcd_wait in pmcd_wait_l:
            pmcd_wait.wait()
            if pmcd_wait.returncode != 0:
                self.logger.error(
                    "Pmcd_wait process failed to connect to pmcd on"
                    " host %s:55677 after 30 seconds, %r",
                    host,
                    pmcd_wait.returncode,
                )
                errors += 1
        if errors > 0:
            return

        # Now that we have verified all the pmcd processes are running, we
        # create the pmproxy process ahead of all the loggers so that it can
        # send metrics to the Redis server as they arrive..
        conf_path = str(self.templates_path / "pmproxy.conf")
        args = [
            self.pmproxy_path,
            "--log=-",
            "--foreground",
            "--timeseries",
            "--port=44566",
            f"--redishost={self.redis_host}",
            f"--redisport={self.redis_port}",
            f"--config={conf_path}",
        ]
        env = os.environ.copy()
        env["PCP_ARCHIVE_DIR"] = data_dir
        self.logger.debug("Starting pmporxy, cwd %s, args %r", self.tool_dir, args)
        with (self.tool_dir / "pmproxy-proc.log").open("w") as pmproxy_logs:
            try:
                run = subprocess.Popen(
                    args,
                    cwd=self.tool_dir,
                    stdout=pmproxy_logs,
                    stderr=subprocess.STDOUT,
                    env=env,
                )
            except Exception as exc:
                self.logger.error("Pmproxy run process failed: '%s', %r", exc, args)
            else:
                self.run_pmproxy = run

        # Finally, create all the loggers.
        for host in self.host_tools_dict:
            label = self.host_tools_dict[host]["label"]
            if label:
                label = f"{label}:"
            host_dir = data_dir / f"{label}{host}"
            log_dir = self.tool_dir / host
            args = [
                self.pmlogger_path,
                "--log=-",
                "--report",
                "-t",
                "3s",  # FIXME: take from tools interval
                "-c",
                str(self.templates_path / "pmlogger.conf"),
                f"--host={host}:55677",
                f"{host_dir}/%Y%m%d.%H.%M",
            ]
            self.logger.debug("Starting pmlogger, cwd %s, args %r", log_dir, args)
            with (log_dir / "pmlogger-proc.log").open("a+") as pmlogger_logs:
                try:
                    run = subprocess.Popen(
                        args,
                        cwd=log_dir,
                        stdout=pmlogger_logs,
                        stderr=subprocess.STDOUT,
                    )
                except Exception as exc:
                    self.logger.error(
                        "Pmlogger run process failed: '%s', %r", exc, args
                    )
                else:
                    self.run.append(run)

    def terminate(self):
        """terminate - shuts down the PCP collector, and creates a tar ball of
        the collected data.
        """
        try:
            super().terminate()
        except Exception:
            self.logger.error("Pmlogger failed to terminate")
            return
        finally:
            try:
                self.run_pmproxy.terminate()
                sts = self.run_pmproxy.wait()
            except Exception as exc:
                self.logger.error("Failed to terminate pmproxy process: '%s'", exc)
            else:
                if sts != 0:
                    self.logger.warning("Pmproxy process terminated with %d", sts)

        self.logger.debug("Pmproxy and pmlogger(s) terminated")

        args = [
            self.tar_path,
            "--remove-files",
            "-Jcf",
            f"{self.tool_group_dir}/pcp_data.tar.xz",
            "-C",
            f"{self.tool_group_dir}/",
            "pcp",
        ]
        cp = subprocess.run(args)
        if cp.returncode != 0:
            self.logger.warning("Failed to tar up pmlogger data: %r", args)


class JaegerCollector(BaseCollector):
    """Persistent tool data collector for Jaeger tracing"""

    name = "jaeger"

    def __init__(self, *args, **kwargs):
        """Constructor - responsible for setting up the particulars for the
        Jaeger collector.
        """
        self.jaeger_path = find_executable("jaeger-all-in-one")
        if self.jaeger_path is None:
            raise ToolDataSinkError("External 'jaeger' executable not found")

        super().__init__(*args, **kwargs)
        self.tool_context = []
        for host, tools in sorted(self.host_tools_dict.items()):
            for tool in sorted(tools["names"]):
                port = self.tool_metadata.getProperties(tool)["port"]
                self.tool_context.append(
                    dict(hostname=f"{host}_{tool}", hostport=f"{host}:{port}")
                )
        if not self.tool_context:
            raise ToolDataSinkError("Expected Jaeger persistent tool context not found")

    def launch(self):
        """launch - creates the YAML file that directs Jaeger's behavior,
        the directory Jaeger will write its data, and creates the sub-
        process that runs Jaeger.
        """
        try:
            self._mk_tool_dir()
        except Exception:
            return

        args = [self.jaeger_path]
        with (self.tool_dir / "jaeger.log").open("w") as jaeger_logs:
            try:
                # modify subprocess's environment to include variables for Badger storage
                my_env = os.environ.copy()
                my_env["SPAN_STORAGE_TYPE"] = "badger"
                my_env["BADGER_EPHEMERAL"] = "false"
                my_env["BADGER_DIRECTORY_VALUE"] = str(
                    self.tool_dir / "badger" / "data"
                )
                my_env["BADGER_DIRECTORY_KEY"] = str(self.tool_dir / "badger" / "key")

                run = subprocess.Popen(
                    args,
                    cwd=self.tool_dir,
                    stdout=jaeger_logs,
                    stderr=jaeger_logs,
                    env=my_env,
                )
            except Exception as exc:
                self.logger.error("Jaeger process creation failed: '%s', %r", exc, args)
                return
            else:
                self.run.append(run)

    def terminate(self):
        """terminate - shuts down the jaeger sub-process, and creates a
        tar ball of the data collected.
        """
        try:
            super().terminate()
        except Exception:
            self.logger.error("Jaeger failed to terminate")
            return

        self.logger.debug("Jaeger terminated")

        args = [
            self.tar_path,
            "--remove-files",
            "-Jcf",
            f"{self.tool_group_dir}/jaeger_data.tar.xz",
            "-C",
            f"{self.tool_group_dir}/",
            "jaeger",
        ]
        cp = subprocess.run(args)
        if cp.returncode != 0:
            self.logger.warning("Failed to tar up Jaeger data: %r", args)


class BenchmarkRunDir:
    """BenchmarkRunDir - helper class for handling the benchmark_run_dir
    directory Redis parameter vs the actual "local" benchmark run directory.

    It is a requirement of the Tool Meister sub-system that the ${pbench_run}
    directory is always a prefix of the ${benchmark_run_dir}.

    When the pbench CLI starts the Tool Data Sink directly, the local
    benchmark run directory is the same as the value of the benchmark_run_dir
    parameter.

    But when the Tool Data Sink runs in a container, the path to the benchmark
    run directory inside the container might be different from the parameter
    value because the mount point for the external file system has a different
    path inside the container.  Typically, the container is constructed with
    the default pbench installation, where the ${pbench_run} directory is
    "/var/lib/pbench-agent".

    The entity responsible for starting the Tool Data Sink container typically
    mounts a different directory for /var/lib/pbench-agent via 'podman run
    --volume /srv/data/pbench-run-dir:/var/lib/pbench-agent:Z'.  This leads to
    a conflict where the external ${pbench_run} path is different from the
    internal-to-the-container ${pbench_run} path.  To resolve this, the entity
    which creates the external pbench run directory creates a ".path" file in
    that directory containing the full "external" path to the pbench run
    directory. The Tool Data Sink uses that path to validate that external
    benchmark_run_dir parameter values are valid.

    This class implements the mechanism that allows the Tool Data Sink code to
    handle that seamlessly.
    """

    class Exists(Exception):
        pass

    class Prefix(Exception):
        pass

    def __init__(self, ext_benchmark_run_dir, int_pbench_run):
        self._ext_benchmark_run_dir = Path(ext_benchmark_run_dir)
        self._ext_pbench_run = self._ext_benchmark_run_dir.parent
        self._int_pbench_run = Path(int_pbench_run)

        # The Tool Data Sink could be running in a container. If so, then
        # it'll be using the default benchmark run directory.  If the
        # benchmark_run_dir parameter is valid, there will be a file
        # called ".path" in the default benchmark run directory which will
        # match.
        #
        # E.g.:
        #  $ pbench_run="/home/<USER>/run-dir"
        #  $ benchmark_run_dir="${pbench_run}/script_config_<date>"
        #  $ cat ${pbench_run}/.path
        #  /home/<USER>/run-dir
        #  $ podman run --volume ${pbench_run}:/var/lib/pbench-agent \
        #    pbench-agent-tool-data-sink bash
        #  [ abcdefg /]$ cat /var/lib/pbench-agent/.path
        #  /home/<USER>/run-dir
        try:
            benchmark_run_dir_lcl = self._ext_benchmark_run_dir.resolve(strict=True)
        except Exception:
            # Might be in a container; let's first construct the
            # internal-to-the-container benchmark run directory.
            benchmark_run_dir_lcl = (
                self._int_pbench_run / self._ext_benchmark_run_dir.name
            )
            dot_path = self._int_pbench_run / ".path"
            try:
                dot_path_contents = dot_path.read_text().strip()
            except Exception as exc:
                # Failed to read ".path" contents, give up.
                raise ToolDataSinkError(
                    f"Run directory parameter, '{ext_benchmark_run_dir}', must"
                    f" be an existing directory ('{self._ext_pbench_run}/"
                    f".path' not found, '{exc}').",
                )
            else:
                if dot_path_contents != str(self._ext_pbench_run):
                    raise ToolDataSinkError(
                        f"Run directory parameter, '{ext_benchmark_run_dir}',"
                        " must be an existing directory (.path contents"
                        f" mismatch, .path='{dot_path_contents}' !="
                        f" '{self._ext_pbench_run}').",
                    )
        else:
            # We can access the benchmark_run_dir directly, no need to
            # consider contents of ".path" file.
            pass
        if not benchmark_run_dir_lcl.is_dir():
            raise ToolDataSinkError(
                f"Run directory parameter, '{ext_benchmark_run_dir}', must be"
                " a real directory.",
            )
        self.local = benchmark_run_dir_lcl

    def __str__(self):
        """__str__ - the string representation of a BenchmarkRunDir object is
        the original external benchmark run directory string.
        """
        return str(self._ext_benchmark_run_dir)

    def validate(self, directory):
        """validate - check that an external directory has a prefix of the external
        benchmark run directory.
        """
        directory_p = Path(directory)
        try:
            # Check that "directory" has a prefix of
            rel_path = directory_p.relative_to(self._ext_benchmark_run_dir)
        except ValueError:
            raise self.Prefix()
        local_dir = self.local / rel_path
        if not local_dir.is_dir():
            # The internal benchmark run directory does not have the same
            # sub-directory hierarchy.
            raise self.Exists()
        return local_dir


class ToolDataSink(Bottle):
    """ToolDataSink - sub-class of Bottle representing state for tracking data
    sent from tool meisters via an HTTP PUT method.
    """

    # The list of actions where we expect Tool Meisters to send data to us.
    _data_actions = frozenset(("send", "sysinfo"))

    @staticmethod
    def fetch_params(params, pbench_run):
        try:
            _benchmark_run_dir = params["benchmark_run_dir"]
            bind_hostname = params["bind_hostname"]
            port = params["port"]
            channel_prefix = params["channel_prefix"]
            tool_group = params["group"]
            tool_metadata = ToolMetadata.tool_md_from_dict(params["tool_metadata"])
            tool_trigger = params["tool_trigger"]
            tools = params["tools"]
        except KeyError as exc:
            raise ToolDataSinkError(f"Invalid parameter block, missing key {exc}")
        else:
            benchmark_run_dir = BenchmarkRunDir(_benchmark_run_dir, pbench_run)
            return (
                benchmark_run_dir,
                bind_hostname,
                port,
                channel_prefix,
                tool_group,
                tool_metadata,
                tool_trigger,
                tools,
            )

    def __init__(
        self,
        pbench_bin,
        pbench_run,
        hostname,
        tar_path,
        cp_path,
        redis_server,
        redis_host,
        redis_port,
        params,
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
        self.tar_path = tar_path
        self.cp_path = cp_path
        self.redis_server = redis_server
        self.redis_host = redis_host
        self.redis_port = redis_port
        ret_val = self.fetch_params(params, pbench_run)
        (
            self.benchmark_run_dir,
            self.bind_hostname,
            self.port,
            self.channel_prefix,
            self.tool_group,
            self.tool_metadata,
            self.tool_trigger,
            self.tools,
        ) = ret_val
        self.optional_md = optional_md
        self.logger = logger
        # Initialize internal state
        self.action = None
        self.data_ctx = None
        self.directory = None
        self._server = None
        self._jaeger_server = None
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
        self._tm_log_capture_thread_cv = Condition(lock=self._lock)
        self._tm_log_capture_thread_state = None
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
            host=self.bind_hostname, port=self.port, logger=self.logger
        )
        self.web_server_thread = Thread(target=self.web_server_run)
        self.web_server_thread.start()
        err_text, err_code = self._server.wait()
        if err_code > 0:
            # Pass along the OSError with its errno, let's us handle cleanly
            # EADDRINUSE errors.
            raise OSError(err_code, err_text)
        elif err_code < 0:
            # All other errors encountered by the WSGI thread are already
            # logged.
            raise ToolDataSinkError(f"Failure to create WSGI server - {err_text!r}")
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
        with self._lock:
            while self._tm_log_capture_thread_state is None:
                self._tm_log_capture_thread_cv.wait()
        if self._tm_log_capture_thread_state != "started":
            self.logger.warning(
                "'tm_log_capture' thread failed to start, not processing Tool"
                " Meister logs ..."
            )
        else:
            self.logger.debug(
                "'tm_log_capture' thread started, processing Tool Meister logs ..."
            )

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
        tm_log_file = self.benchmark_run_dir.local / "tm" / "tm.logs"
        with tm_log_file.open("w") as fp:
            try:
                with self._lock:
                    self._tm_log_capture_thread_state = "started"
                    self._tm_log_capture_thread_cv.notify()
                for log_msg in self._to_logging_chan.fetch_message(logger):
                    fp.write(f"{log_msg}\n")
                    fp.flush()
            except redis.ConnectionError:
                # We don't bother reporting any connection errors.
                pass
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

        The first thing we have to do is to determine which tools are no-ops,
        transient, and persistent, and properly record the initial "posted"
        state.

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
            failed_tools = []
            for tool_name in tools.keys():
                try:
                    code, msg = tm["installs"][tool_name]
                except KeyError:
                    code, msg = 0, ""
                if code != 0:
                    failed_tools.append(tool_name)
                elif tool_name in persistent_tools_l:
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
            tm["failed_tools"] = failed_tools

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
            dst = str(self.benchmark_run_dir.local / "ssh.config")
            try:
                shutil.copyfile(src, dst)
            except FileNotFoundError:
                pass
            except Exception as exc:
                self.logger.warning("failed to copy %s to %s: %s", src, dst, exc)
        # cp -L  /etc/ssh/ssh_config   ${dir}/ > /dev/null 2>&1
        etc_ssh = Path("/etc") / "ssh"
        src = str(etc_ssh / "ssh_config")
        dst = str(self.benchmark_run_dir.local / "ssh_config")
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
            [
                self.cp_path,
                "-rL",
                "/etc/ssh/ssh_config.d",
                f"{self.benchmark_run_dir.local}/",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        mdlog_name = self.benchmark_run_dir.local / "metadata.log"
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
        mdlog.set(section, "name", self.benchmark_run_dir.local.name.replace("%", "%%"))
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
        mdlog.set(section, "hostname-i", hostdata["i"].replace("%", "%%"))
        mdlog.set(section, "hostname-A", hostdata["A"])
        mdlog.set(section, "hostname-I", hostdata["I"].replace("%", "%%"))
        mdlog.set(section, "ssh_opts", self.optional_md["ssh_opts"])

        section = "run"
        mdlog.add_section(section)
        mdlog.set(section, "controller", self.hostname)
        mdlog.set(section, "start_run", _now("start"))

        section = "tools"
        mdlog.add_section(section)
        mdlog.set(section, "hosts", " ".join(sorted(list(self.tools.keys()))))
        mdlog.set(section, "group", self.tool_group)
        mdlog.set(section, "trigger", str(self.tool_trigger).replace("%", "%%"))

        for host, tm in sorted(tms.items()):
            section = f"tools/{host}"
            mdlog.add_section(section)
            mdlog.set(section, "label", tm["label"])
            tools_string = ",".join(sorted(list(tm["tools"].keys())))
            mdlog.set(section, "tools", tools_string)

            # add host data
            mdlog.set(section, "hostname-s", tm["hostname_s"])
            mdlog.set(section, "hostname-f", tm["hostname_f"])
            mdlog.set(section, "hostname-i", tm["hostname_i"].replace("%", "%%"))
            mdlog.set(section, "hostname-A", tm["hostname_A"])
            mdlog.set(section, "hostname-I", tm["hostname_I"].replace("%", "%%"))
            ver, seq, sha = tm["version"], tm["seqno"], tm["sha1"]
            rpm_version = f"v{ver}-{seq}g{sha}"
            try:
                rpm_versions[rpm_version] += 1
            except KeyError:
                rpm_versions[rpm_version] = 1
            mdlog.set(section, "rpm-version", rpm_version)

            for tool, opts in tm["tools"].items():
                # Compatibility - keep each tool with options listed
                mdlog.set(section, tool, opts.replace("%", "%%"))

                # New way is to give each tool a separate section storing the
                # options and install results individually.
                new_section = f"tools/{host}/{tool}"
                mdlog.add_section(new_section)
                mdlog.set(new_section, "options", opts.replace("%", "%%"))
                try:
                    code, msg = tm["installs"][tool]
                except KeyError:
                    pass
                else:
                    mdlog.set(new_section, "install_check_status_code", str(code))
                    mdlog.set(
                        new_section, "install_check_output", msg.replace("%", "%%")
                    )

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
                raise ToolDataSinkError(
                    "Tool Data Sink started, but nobody is listening"
                )
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
                # Ignore any Tool Meisters which do not have any transient
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
            mdlog_name = self.benchmark_run_dir.local / "metadata.log"
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
                iterations = self.benchmark_run_dir.local / ".iterations"
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

        try:
            local_dir = self.benchmark_run_dir.validate(directory_str)
        except self.benchmark_run_dir.Prefix:
            self.logger.error(
                "action '%s' with invalid directory, '%s' (not a sub-directory of '%s')",
                action,
                directory_str,
                self.benchmark_run_dir,
            )
            self._send_client_status(action, "directory not a sub-dir of run directory")
            return
        except self.benchmark_run_dir.Exists:
            self.logger.error(
                "action '%s' with invalid directory, '%s' (does not exist)",
                action,
                directory_str,
            )
            self._send_client_status(action, "directory does not exist")
            return
        else:
            assert local_dir is not None, f"Logic bomb!  local_dir = {local_dir!r}"

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
                jaeger_tool_dict = {}
                for tm in self._tm_tracking:
                    prom_tools = []
                    pcp_tools = []
                    jaeger_tools = []
                    persist_tools = self._tm_tracking[tm]["persistent_tools"]
                    for tool in persist_tools:
                        tool_data = self.tool_metadata.getProperties(tool)
                        if tool_data["collector"] == "prometheus":
                            prom_tools.append(tool)
                        elif tool_data["collector"] == "pcp":
                            pcp_tools.append(tool)
                        elif tool_data["collector"] == "jaeger":
                            jaeger_tools.append(tool)
                    if len(prom_tools) > 0:
                        prom_tool_dict[self._tm_tracking[tm]["hostname"]] = {
                            "label": self._tm_tracking[tm]["label"],
                            "names": prom_tools,
                        }
                    if len(pcp_tools) > 0:
                        pcp_tool_dict[self._tm_tracking[tm]["hostname"]] = {
                            "label": self._tm_tracking[tm]["label"],
                            "names": pcp_tools,
                        }
                    if len(jaeger_tools) > 0:
                        jaeger_tool_dict[self._tm_tracking[tm]["hostname"]] = {
                            "label": self._tm_tracking[tm]["label"],
                            "names": jaeger_tools,
                        }
                if prom_tool_dict or pcp_tool_dict or jaeger_tool_dict:
                    tool_names = list(prom_tool_dict.keys())
                    tool_names.extend(list(pcp_tool_dict.keys()))
                    tool_names.extend(list(jaeger_tool_dict.keys()))
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
                        self.tar_path,
                        logger=self.logger,
                    )
                    self._prom_server.launch()
                if pcp_tool_dict:
                    self.logger.debug(
                        "init pcp tools for tool meisters: %s",
                        ", ".join(sorted(list(pcp_tool_dict.keys()))),
                    )
                    self._pcp_server = PcpCollector(
                        self.pbench_bin,
                        self.benchmark_run_dir,
                        self.tool_group,
                        pcp_tool_dict,
                        self.tool_metadata,
                        self.tar_path,
                        redis_host=self.redis_host,
                        redis_port=self.redis_port,
                        logger=self.logger,
                    )
                    self._pcp_server.launch()
                if jaeger_tool_dict:
                    self._jaeger_server = JaegerCollector(
                        self.pbench_bin,
                        self.benchmark_run_dir,
                        self.tool_group,
                        jaeger_tool_dict,
                        self.tool_metadata,
                        self.tar_path,
                        logger=self.logger,
                    )
                    self._jaeger_server.launch()
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
                if self._jaeger_server:
                    self._jaeger_server.terminate()
            elif action in self._data_actions:
                # The remote Tool Meisters will be hashing the directory
                # argument this way when invoking the PUT method.  They just
                # consider the directory argument to be an opaque context.
                # The Tool Data Sink, writes the data it receives to that
                # directory, but expect them to provide the opaque context in
                # the URL for the PUT method.
                directory_bytes = directory_str.encode("utf-8")
                self.data_ctx = hashlib.md5(directory_bytes).hexdigest()
                self.directory = local_dir

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
                        [self.tar_path, "-xf", host_data_tb_name],
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


def get_logger(PROG, daemon=False):
    """get_logger - construct a logger for a Tool Meister instance.

    If in the Unit Test environment, just log to console.
    If in non-unit test environment:
       If daemonized, log to syslog and log back to Redis.
       If not daemonized, log to console AND log back to Redis
    """
    logger = logging.getLogger(PROG)
    if os.environ.get("_PBENCH_TOOL_DATA_SINK_LOG_LEVEL") == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logger.setLevel(log_level)

    unit_tests = bool(os.environ.get("_PBENCH_UNIT_TESTS"))
    if unit_tests or not daemon:
        sh = logging.StreamHandler()
    else:
        sh = logging.FileHandler(f"{PROG}.log")
    sh.setLevel(log_level)
    shf = logging.Formatter(fmtstr_ut if unit_tests else fmtstr)
    sh.setFormatter(shf)
    logger.addHandler(sh)

    return logger


def driver(
    PROG,
    redis_server,
    redis_host,
    redis_port,
    pbench_bin,
    pbench_run,
    hostname,
    tar_path,
    cp_path,
    param_key,
    params,
    optional_md,
    logger=None,
):
    if logger is None:
        logger = get_logger(PROG)

    logger.debug("params_key (%s): %r", param_key, params)

    try:
        with ToolDataSink(
            pbench_bin,
            pbench_run,
            hostname,
            tar_path,
            cp_path,
            redis_server,
            redis_host,
            redis_port,
            params,
            optional_md,
            logger,
        ) as tds_app:
            tds_app.execute()
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            logger.error(
                "ERROR - tool data sink failed to start, %s:%s already in use",
                params["bind_hostname"],
                params["port"],
            )
            ret_val = 8
        else:
            logger.exception("ERROR - failed to start the tool data sink")
            ret_val = 9
    except Exception:
        logger.exception("ERROR - failed to start the tool data sink")
        ret_val = 10
    else:
        ret_val = 0
    return ret_val


def daemon(
    PROG,
    redis_server,
    redis_host,
    redis_port,
    pbench_bin,
    pbench_run,
    hostname,
    tar_path,
    cp_path,
    param_key,
    params,
    optional_md,
):
    # Disconnect any existing connections to the Redis server.
    redis_server.connection_pool.disconnect()
    del redis_server

    # Before we daemonize, flush any data written to stdout or stderr.
    sys.stderr.flush()
    sys.stdout.flush()

    pidfile_name = f"{PROG}.pid"
    pfctx = pidfile.PIDFile(pidfile_name)
    with open(f"{PROG}.out", "w") as sofp, open(
        f"{PROG}.err", "w"
    ) as sefp, DaemonContext(
        stdout=sofp,
        stderr=sefp,
        working_directory=os.getcwd(),
        umask=0o022,
        pidfile=pfctx,
    ):
        logger = get_logger(PROG, daemon=True)

        # We have to re-open the connection to the redis server now that we
        # are "daemonized".
        logger.debug("re-constructing Redis server object")
        try:
            redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)
        except Exception as e:
            logger.error(
                "Unable to construct Redis server object, %s:%s: %s",
                redis_host,
                redis_port,
                e,
            )
            return 7
        else:
            logger.debug("reconstructed Redis server object")
        return driver(
            PROG,
            redis_server,
            redis_host,
            redis_port,
            pbench_bin,
            pbench_run,
            hostname,
            tar_path,
            cp_path,
            param_key,
            params,
            optional_md,
            logger=logger,
        )


def main(argv):
    _prog = Path(argv[0])
    PROG = _prog.name
    # The Tool Data Sink executable is in:
    #   ${pbench_bin}/util-scripts/tool-meister/pbench-tool-data-sink
    # So .parent at each level is:
    #   _prog       ${pbench_bin}/util-scripts/tool-meister/pbench-tool-data-sink
    #     .parent   ${pbench_bin}/util-scripts/tool-meister
    #     .parent   ${pbench_bin}/util-scripts
    #     .parent   ${pbench_bin}
    pbench_bin = _prog.parent.parent.parent

    try:
        redis_host = argv[1]
        redis_port = argv[2]
        param_key = argv[3]
    except IndexError as e:
        print(f"{PROG}: Invalid arguments: {e}", file=sys.stderr)
        return 1
    else:
        if not redis_host or not redis_port or not param_key:
            print(f"{PROG}: Invalid arguments: {argv!r}", file=sys.stderr)
            return 1
    try:
        daemonize = argv[4]
    except IndexError:
        daemonize = "no"

    tar_path = find_executable("tar")
    if tar_path is None:
        print("External 'tar' executable not found", file=sys.stderr)
        return 2

    cp_path = find_executable("cp")
    if cp_path is None:
        print("External 'cp' executable not found", file=sys.stderr)
        return 2

    try:
        pbench_run = os.environ["pbench_run"]
    except KeyError:
        print(
            "Unable to fetch pbench_run environment variable", file=sys.stderr,
        )
        return 3

    try:
        redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)
    except Exception as e:
        print(
            f"Unable to connect to redis server, {redis_host}:{redis_port}: {e}",
            file=sys.stderr,
        )
        return 4

    try:
        hostname = os.environ["_pbench_full_hostname"]
    except KeyError:
        print(
            "Unable to fetch _pbench_full_hostname environment variable",
            file=sys.stderr,
        )
        return 5

    try:
        # Wait for the parameter key value to show up.
        params_str = wait_for_conn_and_key(redis_server, param_key, PROG)
        # The expected parameters for this "data-sink" is what "channel" to
        # subscribe to for the tool meister operational life-cycle.  The
        # data-sink listens for the actions, sysinfo | init | start | stop |
        # send | end | terminate, exiting when "terminate" is received,
        # marking the state in which data is captured.
        #
        # E.g. params = '{ "channel_prefix": "some-prefix",
        #                  "benchmark_run_dir": "/loo/goo" }'
        params = json.loads(params_str)
        ToolDataSink.fetch_params(params, pbench_run)
    except Exception as ex:
        print(
            f"Unable to fetch and decode parameter key, {param_key}: {ex}",
            file=sys.stderr,
        )
        return 6

    optional_md = params.get("optional_md", dict())

    func = daemon if daemonize == "yes" else driver
    ret_val = func(
        PROG,
        redis_server,
        redis_host,
        redis_port,
        pbench_bin,
        pbench_run,
        hostname,
        tar_path,
        cp_path,
        param_key,
        params,
        optional_md,
    )
    return ret_val
