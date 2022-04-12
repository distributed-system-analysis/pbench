"""Tests for the Tool Meister module.
"""

from http import HTTPStatus
import io
import logging
from pathlib import Path
import pytest
import responses
import shutil
import signal
import subprocess
from typing import Any, List, NamedTuple, Tuple

from pbench.agent.tool_meister import (
    log_raw_io_output,
    Tool,
    TransientTool,
    PcpTransientTool,
    PersistentTool,
    DcgmTool,
    NodeExporterTool,
    PcpTool,
    ToolException,
    ToolMeister,
    ToolMeisterError,
)


def test_log_raw_io_output(caplog):
    class MockedPipe:
        def readlines(self, hint: int = -1) -> bytes:
            yield b"line1\n"
            yield b"\n"
            yield b"line3\n"
            yield b"line4\n"

    log_raw_io_output(MockedPipe(), logging.getLogger("test_log_raw_io_output"))

    assert caplog.record_tuples[0][2] == "line1"
    assert caplog.record_tuples[1][2] == "line3"
    assert caplog.record_tuples[2][2] == "line4"


class NullObject:
    pass


class MockShutilWhich:
    """Mock shutil.which in the tool_meister module."""

    def __init__(self, find: List[str]):
        """Constructor

        Arguments:

            find:  list of things that should be found
        """
        self.find = frozenset(find)

    def which(self, exec: str) -> str:
        """Mocked version of shutil.which.

        Arguments:

            exec:  A string representing the executable to "look for"

        Returns a "/usr/bin/{exec}" if the exectuable is in the list of things
        to be found, otherwise None.
        """
        return f"/usr/bin/{exec}" if exec in self.find else None


def mock_shutil_which(monkeypatch, find: List[str] = []):
    """Encapsulate steps to mock out shutil.which.

    Arguments:

        monkeypatch:  the monkeypatch instance to use
        find:  list of things that should be found
    """
    msw = MockShutilWhich(find)

    monkeypatch.setattr(shutil, "which", msw.which)


class MockedPath:
    """Minimal mocked Path object."""

    def __init__(self, exists: bool = True, path: str = "/foo/bar"):
        self._exists = exists
        self._path = path

    def is_dir(self) -> bool:
        return self._exists

    def exists(self) -> bool:
        return self._exists

    def mkdir(self):
        return

    def __str__(self) -> str:
        return self._path

    def __eq__(self, other) -> bool:
        return self._path == str(other)

    def __repr__(self) -> str:
        return f"'{self._path}'"

    def __truediv__(self, path: str):
        return MockedPath(self._exists, f"{self._path}/{path}")


class MockProcessBasic:
    """A mocked process object which only allows us to control when
    the subprocess.TimeoutExpired exceptions are raised.
    """

    def __init__(self, success_on=None):
        assert success_on is None or success_on > 0
        # Tracks how many times the .wait() method is called.
        self.wait_calls = 0
        # On which call to the .wait() method will it return a status code.
        self.success_on = success_on

    def wait(self, timeout: Any = None) -> int:
        """Return 42 when the number of wait calls is equal to the number of
        "success on" wait calls, if specified.

        Raises a subprocess.TimeoutExpired() exception otherwise.
        """
        self.wait_calls += 1
        if self.wait_calls == self.success_on:
            return 42
        raise subprocess.TimeoutExpired("command", 43)


class MockStdfd:
    """Track .close() method calls on std* objects."""

    def __init__(self):
        self.closed = False

    def close(self) -> bool:
        self.closed = True


class MockProcess:
    """A mocked process object to verify behaviors taken by
    Tool._wait_for_process_with_kill() method.
    """

    def __init__(self, raise_timeout: bool = False):
        self.raise_timeout = raise_timeout
        self.kill_called = False
        self.wait_called = False
        self.wait_timeout = None

        self.stdin = MockStdfd()
        self.stdout = MockStdfd()
        self.stderr = MockStdfd()

    def kill(self):
        self.kill_called = True

    def wait(self, timeout: int = None):
        self.wait_called = True
        self.wait_timeout = timeout
        if self.raise_timeout:
            raise subprocess.TimeoutExpired("command", 43)


class MockCreatedProcess:
    """Track arguments passed to Tool._create_process_with_logger()."""

    def __init__(self, args, tool_dir, ctx_name):
        self.args = args
        self.tool_dir = tool_dir
        self.ctx_name = ctx_name


def mocked_create_process_with_logger(
    args: List[str], tool_dir: MockedPath, ctx_name: str = None
) -> MockCreatedProcess:
    """Mock the behavior of Tool._create_process_with_logger() by just
    recording what arguments we given in a tracking object.

    Returns a tracking object as the "process".
    """
    return MockCreatedProcess(args, tool_dir, ctx_name)


class MockProcessForTerminate:
    """A mock for process objects which just need to know if its
    ".terminate()" method was called.
    """

    def __init__(self, raise_exc: bool = False):
        self.terminate_called = False
        self.raise_exc = raise_exc

    def terminate(self):
        self.terminate_called = True
        if self.raise_exc:
            raise Exception("Terminate")


class TestTool:
    @staticmethod
    def test_constructor_and_interfaces():
        mocked_install_dir = MockedPath()
        mocked_logger = NullObject()
        tool = Tool("test-tool", "opt1;opt2", mocked_install_dir, mocked_logger)
        assert tool._tool_type is None

        with pytest.raises(NotImplementedError):
            tool.install()
        with pytest.raises(NotImplementedError):
            tool.start(MockedPath())
        with pytest.raises(NotImplementedError):
            tool.stop()
        with pytest.raises(NotImplementedError):
            tool.wait()

        pi_dir = MockedPath(exists=False)
        with pytest.raises(ToolException) as excinfo:
            Tool(name="who", tool_opts="cares", pbench_install_dir=pi_dir, logger=None)
        assert (
            str(excinfo.value)
            == f"pbench installation directory does not exist: {pi_dir}"
        )

    @staticmethod
    def test_create_process_with_logger(monkeypatch):
        # First we need a mock of the subprocess.Popen() constructor, which
        # will just record what the constructor was called with.
        class MockPopen:
            def __init__(self, args, cwd=None, stdin=None, stdout=None, stderr=None):
                self.args = args
                self.cwd = cwd
                self.stdin = stdin
                self.stdout = stdout
                self.stderr = stderr

        monkeypatch.setattr("subprocess.Popen", MockPopen)

        # Next we need a mock of the threading.Thread() constructor, which
        # will also just record what it was called with, and also offer the
        # "daemon" field, and a "start()" method to be called.
        the_thread = None

        class MockThread:
            def __init__(self, target: Any = None, args: Any = None):
                self.target = target
                self.args = args
                self.daemon = False
                self.start_called = False
                nonlocal the_thread
                the_thread = self

            def start(self):
                self.start_called = True

        monkeypatch.setattr("threading.Thread", MockThread)

        # Finally we need mocked out arguments to the Tool() constructor so
        # that we can check the mocks above were used as expected.
        class MockedLogger:
            def getChild(self, arg: Any) -> str:
                return f"parent.child({arg})"

        mocked_install_dir = MockedPath()
        mocked_logger = MockedLogger()
        tool = Tool("test-tool", "opt1;opt2", mocked_install_dir, mocked_logger)

        # Now we can invoke the method under test with some fake arguments to
        # verify it does the right thing.
        args = ["command", "arg1", "arg2"]
        cwd = MockedPath()
        process = tool._create_process_with_logger(args, cwd)

        assert the_thread is not None
        assert the_thread.target is log_raw_io_output
        assert the_thread.args == (subprocess.PIPE, "parent.child(logger)")
        assert the_thread.daemon is True
        assert the_thread.start_called is True

        assert process.args is args
        assert process.cwd is cwd
        assert process.stdin == subprocess.DEVNULL
        assert process.stdout == subprocess.PIPE
        assert process.stderr == subprocess.STDOUT

        # And we do it again with a "ctx" argument value.
        the_thread = None
        process = tool._create_process_with_logger(args, cwd, ctx="foo")
        assert the_thread.args == (subprocess.PIPE, "parent.child(logger-foo)")

    @staticmethod
    def setup_wait_for_process_tool(logger_name: str) -> Tool:
        """Provide a Tool() object with a real logger."""
        mocked_install_dir = MockedPath()
        a_logger = logging.getLogger(f"TestTool.{logger_name}")
        return Tool("test-tool", "opt1;opt2", mocked_install_dir, a_logger)

    @staticmethod
    @pytest.mark.parametrize(
        "waits,ctx_name,expected_log_entries,expected_sts,seconds",
        [
            # 1 wait, 0 log entries
            (1, None, 0, 42, None),
            # 2 waits, 1 log entry
            (2, None, 1, 42, "5"),
            # 7 waits, 5 log entries
            (7, None, 5, None, "25"),
            # 1 wait, 0 log entries
            (1, "ctx-a", 0, 42, None),
            # 2 waits, 1 log entry
            (2, "ctx-b", 1, 42, "5"),
            # 7 waits, 5 log entries
            (7, "ctx-c", 5, None, "25"),
        ],
    )
    def test_wait_for_process(
        waits, ctx_name, expected_log_entries, expected_sts, seconds, caplog
    ):
        _ctx_name = "" if ctx_name is None else f",ctx_name={ctx_name}"
        tool = TestTool.setup_wait_for_process_tool(
            f"test_wait_for_process;waits={waits}{_ctx_name}"
        )
        sts = tool._wait_for_process(MockProcessBasic(waits), ctx_name=ctx_name)
        assert sts == expected_sts
        assert len(caplog.record_tuples) == expected_log_entries
        if expected_log_entries > 0:
            _ctx_name = "" if ctx_name is None else f" {ctx_name}"
            assert (
                caplog.record_tuples[-1][2]
                == f"None tool test-tool{_ctx_name} has not stopped after {seconds} seconds"
            )
            assert caplog.record_tuples[-1][1] == logging.DEBUG

    @staticmethod
    def setup_wait_for_process_tool_with_kill(
        logger_name: str, wait_for_process_ret_val: Any
    ) -> Tool:
        """Provide a Tool object where the ._wait_for_process() method is
        mocked to return a specific value.
        """
        tool = TestTool.setup_wait_for_process_tool(logger_name)

        def wait_for_process(_self, process, ctx_name=None):
            return wait_for_process_ret_val

        tool._wait_for_process = wait_for_process
        return tool

    @staticmethod
    def test_wait_for_process_with_kill_success(caplog):
        """Verify immediate action success case."""
        tool = TestTool.setup_wait_for_process_tool_with_kill(
            "test_wait_for_process_with_kill_success", 0
        )

        expected_log_entries = 1
        proc = MockProcess()
        tool._wait_for_process_with_kill(proc)
        assert not proc.kill_called
        assert not proc.wait_called
        assert not proc.stdin.closed
        assert not proc.stdout.closed
        assert not proc.stderr.closed
        assert len(caplog.record_tuples) == expected_log_entries
        assert caplog.record_tuples[0][2] == "Waiting for None tool test-tool process"
        assert caplog.record_tuples[0][1] == logging.INFO

    @staticmethod
    def test_wait_for_process_with_kill_success_w_context(caplog):
        """Verify immediate action success case with context name."""
        tool = TestTool.setup_wait_for_process_tool_with_kill(
            "test_wait_for_process_with_kill_success_w_context", 0
        )

        expected_log_entries = 1
        proc = MockProcess()
        tool._wait_for_process_with_kill(proc, ctx_name="bar")
        assert not proc.kill_called
        assert not proc.wait_called
        assert not proc.stdin.closed
        assert not proc.stdout.closed
        assert not proc.stderr.closed
        assert len(caplog.record_tuples) == expected_log_entries
        assert (
            caplog.record_tuples[0][2] == "Waiting for None tool test-tool bar process"
        )
        assert caplog.record_tuples[0][1] == logging.INFO

    @staticmethod
    def test_wait_for_process_with_kill_sigterm(caplog):
        """Verify -SIGTERM case is considered success."""
        tool = TestTool.setup_wait_for_process_tool_with_kill(
            "test_wait_for_process_with_kill_sigterm", -(signal.SIGTERM)
        )

        expected_log_entries = 1
        proc = MockProcess()
        tool._wait_for_process_with_kill(proc)
        assert not proc.kill_called
        assert not proc.wait_called
        assert not proc.stdin.closed
        assert not proc.stdout.closed
        assert not proc.stderr.closed
        assert len(caplog.record_tuples) == expected_log_entries
        assert caplog.record_tuples[0][2] == "Waiting for None tool test-tool process"
        assert caplog.record_tuples[0][1] == logging.INFO

    @staticmethod
    def test_wait_for_process_with_kill_error_code(caplog):
        """Verify error code handling."""
        tool = TestTool.setup_wait_for_process_tool_with_kill(
            "test_wait_for_process_with_kill_error_code", 42
        )

        expected_log_entries = 2
        proc = MockProcess()
        tool._wait_for_process_with_kill(proc)
        assert not proc.kill_called
        assert not proc.wait_called
        assert not proc.stdin.closed
        assert not proc.stdout.closed
        assert not proc.stderr.closed
        assert len(caplog.record_tuples) == expected_log_entries
        assert caplog.record_tuples[0][2] == "Waiting for None tool test-tool process"
        assert caplog.record_tuples[0][1] == logging.INFO
        assert (
            caplog.record_tuples[1][2] == "None tool test-tool process failed with 42"
        )
        assert caplog.record_tuples[1][1] == logging.WARNING

    @staticmethod
    def test_wait_for_process_with_kill_no_wait_timeout(caplog):
        """Kill() case with no wait() timeout"""
        tool = TestTool.setup_wait_for_process_tool_with_kill(
            "test_wait_for_process_with_kill_no_wait_timeout", None
        )

        expected_log_entries = 2
        proc = MockProcess(raise_timeout=False)
        tool._wait_for_process_with_kill(proc)
        assert proc.kill_called
        assert proc.wait_called
        assert proc.wait_timeout == 30
        assert not proc.stdin.closed
        assert not proc.stdout.closed
        assert not proc.stderr.closed
        assert len(caplog.record_tuples) == expected_log_entries
        assert caplog.record_tuples[0][2] == "Waiting for None tool test-tool process"
        assert caplog.record_tuples[0][1] == logging.INFO
        assert (
            caplog.record_tuples[1][2]
            == "Killed un-responsive None tool test-tool process"
        )
        assert caplog.record_tuples[1][1] == logging.ERROR

    @staticmethod
    def test_wait_for_process_with_kill_wait_timeout(caplog):
        """Kill case with wait() timeout"""
        tool = TestTool.setup_wait_for_process_tool_with_kill(
            "test_wait_for_process_with_kill_wait_timeout", None
        )

        expected_log_entries = 3
        proc = MockProcess(raise_timeout=True)
        tool._wait_for_process_with_kill(proc)
        assert proc.kill_called
        assert proc.wait_called
        assert proc.wait_timeout == 30
        assert proc.stdin.closed
        assert proc.stdout.closed
        assert proc.stderr.closed
        assert len(caplog.record_tuples) == expected_log_entries
        assert caplog.record_tuples[0][2] == "Waiting for None tool test-tool process"
        assert caplog.record_tuples[0][1] == logging.INFO
        assert (
            caplog.record_tuples[1][2]
            == "Killed un-responsive None tool test-tool process"
        )
        assert caplog.record_tuples[1][1] == logging.ERROR
        assert (
            caplog.record_tuples[2][2]
            == "Killed None tool test-tool process STILL didn't die after waiting another 30 seconds, closing its FDs"
        )
        assert caplog.record_tuples[2][1] == logging.WARNING


class TestTransientTool:
    @staticmethod
    def test_install(monkeypatch):
        mocked_install_dir = MockedPath()
        mocked_logger = NullObject()
        tool = TransientTool(
            name="test-tool",
            tool_opts="opt1;opt2",
            pbench_install_dir=mocked_install_dir,
            logger=mocked_logger,
        )

        class CompletedProcess(NamedTuple):
            returncode: int
            stdout: str

        def mocked_run(args, stdin, stdout, stderr, universal_newlines):
            assert args == ["/foo/bar/tool-scripts/test-tool", "--install", "opt1;opt2"]
            assert stdin is None
            assert stdout is subprocess.PIPE
            assert stderr is subprocess.STDOUT
            assert universal_newlines is True
            return CompletedProcess(returncode=0, stdout="")

        monkeypatch.setattr("subprocess.run", mocked_run)
        ir = tool.install()
        assert ir.returncode == 0
        assert ir.output == ""

    @staticmethod
    def setup_transient_tool(logger_name: str) -> TransientTool:
        mocked_install_dir = MockedPath()
        a_logger = logging.getLogger(f"{__class__}.{logger_name}")
        tool = TransientTool(
            name="test-tool",
            tool_opts="opt1;opt2",
            pbench_install_dir=mocked_install_dir,
            logger=a_logger,
        )
        tool._create_process_with_logger = mocked_create_process_with_logger
        return tool

    @staticmethod
    def test_start(caplog):
        tool = __class__.setup_transient_tool("test_start")

        # First verify tool directory argument check.
        with pytest.raises(ToolException) as excinfo:
            tool.start(MockedPath(exists=False))
        assert str(excinfo.value) == "tool directory does not exist: '/foo/bar'"

        # Verify normal case
        the_tool_dir = MockedPath()
        tool.start(the_tool_dir)
        assert tool.tool_dir is the_tool_dir
        assert tool.start_process.args[0] is tool.tool_script
        assert tool.start_process.args[1] == "--start"
        assert tool.start_process.args[2] == f"--dir={the_tool_dir}"
        assert tool.start_process.args[3] is tool.tool_opts
        assert tool.start_process.tool_dir is the_tool_dir
        assert tool.start_process.ctx_name == "start"
        assert len(caplog.record_tuples) == 1
        assert caplog.record_tuples[0][1] == logging.INFO
        assert (
            caplog.record_tuples[0][2]
            == f"test-tool: start_tool -- {tool.tool_script} --start --dir={the_tool_dir} {tool.tool_opts}"
        )

    @staticmethod
    def test_stop(caplog):
        tool = __class__.setup_transient_tool("test_stop")

        the_tool_dir = MockedPath()
        tool.tool_dir = the_tool_dir
        tool.start_process = "running"
        tool.stop()
        assert tool.stop_process.args[0] is tool.tool_script
        assert tool.stop_process.args[1] == "--stop"
        assert tool.stop_process.args[2] == f"--dir={the_tool_dir}"
        assert tool.stop_process.args[3] is tool.tool_opts
        assert tool.stop_process.tool_dir is the_tool_dir
        assert tool.stop_process.ctx_name == "stop"
        assert len(caplog.record_tuples) == 1
        assert caplog.record_tuples[0][1] == logging.INFO
        assert (
            caplog.record_tuples[0][2]
            == f"test-tool: stop_tool -- {tool.tool_script} --stop --dir={the_tool_dir} {tool.tool_opts}"
        )

    @staticmethod
    @pytest.mark.parametrize("delay_cnt", [99, 100, 101])
    def test_stop_delayed_pid_file(delay_cnt, monkeypatch, caplog):
        """Verify the behavior of waiting for the pid file to show up.

        The algorithm used by `.stop()` is to wait 10 seconds for the pid file
        to come into existence by sleeping 1/10 of a second, and checking for
        the file to exist, each time through the loop for 100 iterations of
        the loop.

        We test the algorithm by executing the mock making the file come into
        existence on the 99th call to Path.exists() (resulting in no warning
        message), on the 100th call to Path.exists() (again no warning
        message), and then on the 101st call to Path.exists() (which won't
        ever happen, so a warning message will be issued).
        """
        tool = __class__.setup_transient_tool(
            f"test_stop_delayed_pid_file:delay_cnt={delay_cnt}"
        )

        exists_cnt = {}

        class MockedPathDelayedExists(MockedPath):
            """Minimal mocked Path object extended to delay reporting a given file
            exists."""

            def __init__(
                self, exists: bool = True, path: str = "/foo/bar", delay_cnt: int = 0
            ):
                super().__init__(exists=exists, path=path)
                self._delay_cnt = delay_cnt
                self._exists_cnt = 0

            def exists(self) -> bool:
                self._exists_cnt += 1
                nonlocal exists_cnt
                exists_cnt[self._path] = self._exists_cnt
                if self._exists_cnt >= self._delay_cnt:
                    return self._exists
                else:
                    return False

            def __truediv__(self, path: str):
                return MockedPathDelayedExists(
                    self._exists, f"{self._path}/{path}", delay_cnt=self._delay_cnt
                )

        the_tool_dir = MockedPathDelayedExists(delay_cnt=delay_cnt)
        the_pid_file = f"{the_tool_dir}/test-tool/test-tool.pid"
        tool.tool_dir = the_tool_dir

        def noop(*args, **kwargs):
            return

        monkeypatch.setattr("time.sleep", noop)

        tool.start_process = "running"

        tool.stop()

        assert (
            len(exists_cnt) == 1
        ), f"Problem - more than one file used, {list(exists_cnt.keys())!r}"
        assert exists_cnt[the_pid_file] == min(delay_cnt, 100)
        expected_logs = 1 if delay_cnt <= 100 else 2
        assert len(caplog.record_tuples) == expected_logs
        # Note the info message is always the "last" log message emitted by
        # the `.stop()` method.
        assert caplog.record_tuples[-1][1] == logging.INFO
        assert (
            caplog.record_tuples[-1][2]
            == f"test-tool: stop_tool -- {tool.tool_script} --stop --dir={the_tool_dir} {tool.tool_opts}"
        )
        if expected_logs == 2:
            # When present the warning message is always emitted first.
            assert caplog.record_tuples[0][1] == logging.WARNING
            assert (
                caplog.record_tuples[0][2]
                == f"Tool(test-tool) pid file, {the_pid_file}, does not exist after waiting 10 seconds"
            )

    @staticmethod
    def test_wait():
        mocked_install_dir = MockedPath()
        a_logger = logging.getLogger(f"{__class__}.test_wait")
        tool = TransientTool(
            name="test-tool",
            tool_opts="opt1;opt2",
            pbench_install_dir=mocked_install_dir,
            logger=a_logger,
        )

        actions = []

        def mocked_wait_for_process_with_kill(process: str, ctx_name: str):
            nonlocal actions
            actions.append((process, ctx_name))

        tool._wait_for_process_with_kill = mocked_wait_for_process_with_kill
        tool.stop_process = "running"
        tool.start_process = "running"

        tool.wait()

        assert tool.stop_process is None
        assert tool.start_process is None
        assert len(actions) == 2
        assert actions[0] == ("running", "stop")
        assert actions[1] == ("running", "start")


class TestPcpTransientTool:
    @staticmethod
    def test_constructor():
        mocked_install_dir = MockedPath()
        mocked_logger = NullObject()
        tool = PcpTransientTool(
            name="tool-transient",
            tool_opts="opt1;opt2",
            pbench_install_dir=mocked_install_dir,
            logger=mocked_logger,
        )
        assert tool._tool_type == "Transient"
        assert tool.name == "tool-transient"
        assert tool.tool_opts == "opt1;opt2"
        assert tool.pbench_install_dir == mocked_install_dir
        assert tool.logger == mocked_logger
        assert tool.pmcd_path is None
        assert tool.pmcd_process is None
        assert tool.pmlogger_path is None
        assert tool.pmlogger_process is None

    @staticmethod
    def test_install(monkeypatch):
        mocked_install_dir = MockedPath()
        mocked_logger = NullObject()
        tool = PcpTransientTool(
            name="tool-transient",
            tool_opts="opt1;opt2",
            pbench_install_dir=mocked_install_dir,
            logger=mocked_logger,
        )

        mock_shutil_which(monkeypatch, ["pmcd", "pmlogger"])

        ir = tool.install()
        assert ir.returncode == 0
        assert ir.output == "pcp tool (pmcd and pmlogger) properly installed"

        mock_shutil_which(monkeypatch, ["pmlogger"])

        ir = tool.install()
        assert ir.returncode == 1
        assert ir.output == "pcp tool (pmcd) not found"

        mock_shutil_which(monkeypatch, ["pmcd"])

        ir = tool.install()
        assert ir.returncode == 1
        assert ir.output == "pcp tool (pmlogger) not found"

    @staticmethod
    def test_start(caplog):
        mocked_install_dir = MockedPath()
        a_logger = logging.getLogger("TestPcpTransientTool.test_start")
        tool = PcpTransientTool(
            name="tool-transient",
            tool_opts="opt1;opt2",
            pbench_install_dir=mocked_install_dir,
            logger=a_logger,
        )
        tool._create_process_with_logger = mocked_create_process_with_logger

        with pytest.raises(ToolException) as excinfo:
            tool.start(MockedPath(False))
        assert str(excinfo.value) == "tool directory does not exist: '/foo/bar'"

        the_tool_dir = MockedPath()
        exp_tool_dir = MockedPath() / "tool"
        tool.pmcd_path = "/usr/bin/pmcd"
        tool.pmlogger_path = "/usr/bin/pmlogger"
        tool.start(the_tool_dir)

        assert tool.pmcd_process.args == [
            "/usr/bin/pmcd",
            "--foreground",
            "--socket=./pmcd.socket",
            "--port=55677",
            f"--config={mocked_install_dir}/templates/pmcd.conf",
        ]
        assert tool.pmlogger_process.args == [
            "/usr/bin/pmlogger",
            "--log=-",
            "--report",
            "-t",
            "3s",
            "-c",
            f"{mocked_install_dir}/templates/pmlogger.conf",
            "--host=localhost:55677",
            f"{the_tool_dir}/tool/%Y%m%d.%H.%M",
        ]
        assert tool.pmcd_process.tool_dir == exp_tool_dir
        assert tool.pmlogger_process.tool_dir == exp_tool_dir
        assert tool.pmcd_process.ctx_name == "pmcd"
        assert tool.pmlogger_process.ctx_name == "pmlogger"

        assert len(caplog.record_tuples) == 1
        assert caplog.record_tuples[0][1] == logging.INFO
        pmcd_args_str = " ".join(tool.pmcd_process.args)
        pmlogger_args_str = " ".join(tool.pmlogger_process.args)
        assert (
            caplog.record_tuples[0][2]
            == f"tool-transient: start_tool -- '{pmcd_args_str}' && '{pmlogger_args_str}'"
        )

    @staticmethod
    def test_stop(caplog):
        mocked_install_dir = MockedPath()
        a_logger = logging.getLogger("TestPcpTransientTool.test_stop")
        tool = PcpTransientTool(
            name="tool-transient",
            tool_opts="opt1;opt2",
            pbench_install_dir=mocked_install_dir,
            logger=a_logger,
        )

        tool.pmcd_process = MockProcessForTerminate()
        tool.pmlogger_process = MockProcessForTerminate()

        tool.stop()

        assert tool.pmcd_process.terminate_called
        assert tool.pmlogger_process.terminate_called

        assert len(caplog.record_tuples) == 1
        assert caplog.record_tuples[0][1] == logging.INFO
        assert caplog.record_tuples[0][2] == "tool-transient: stop_tool"

    @staticmethod
    def test_wait():
        mocked_install_dir = MockedPath()
        a_logger = logging.getLogger("TestPcpTransientTool.test_wait")
        tool = PcpTransientTool(
            name="tool-transient",
            tool_opts="opt1;opt2",
            pbench_install_dir=mocked_install_dir,
            logger=a_logger,
        )

        actions = []

        def mocked_wait_for_process_with_kill(process: str, ctx_name: str):
            nonlocal actions
            actions.append((process, ctx_name))

        tool._wait_for_process_with_kill = mocked_wait_for_process_with_kill
        tool.pmcd_process = "running"
        tool.pmlogger_process = "running"

        tool.wait()

        assert tool.pmcd_process is None
        assert tool.pmlogger_process is None
        assert len(actions) == 2
        assert actions[0] == ("running", "pmcd")
        assert actions[1] == ("running", "pmlogger")


class TestPersistentTool:
    @staticmethod
    def tool_constructor(
        klass: PersistentTool, logger_name: str = None
    ) -> Tuple[MockedPath, Any, PersistentTool]:
        mocked_install_dir = MockedPath()
        mocked_logger = (
            NullObject() if logger_name is None else logging.getLogger("logger_name")
        )
        return (
            mocked_install_dir,
            mocked_logger,
            klass(
                name="test-tool",
                tool_opts="opt1;opt2",
                pbench_install_dir=mocked_install_dir,
                logger=mocked_logger,
            ),
        )

    @staticmethod
    def test_constructor():
        mocked_install_dir, mocked_logger, tool = __class__.tool_constructor(
            PersistentTool
        )
        assert tool._tool_type == "Persistent"
        assert tool.name == "test-tool"
        assert tool.tool_opts == "opt1;opt2"
        assert tool.pbench_install_dir == mocked_install_dir
        assert tool.logger == mocked_logger
        assert tool.args is None
        assert tool.process is None

    @staticmethod
    def test_install_dcgm_exporter(monkeypatch):
        _, _, tool = __class__.tool_constructor(DcgmTool)

        mock_shutil_which(monkeypatch)

        ir = tool.install()

        assert ir.returncode == 1, "dcgm tool (dcgm-exporter) not found"
        assert tool.args is None

        mock_shutil_which(monkeypatch, ["dcgm-exporter"])

        ir = tool.install()

        assert ir.returncode == 0, "dcgm tool (dcgm-exporter) properly installed"
        assert tool.args == ["/usr/bin/dcgm-exporter"]

    @staticmethod
    def test_install_node_exporter(monkeypatch):
        _, _, tool = __class__.tool_constructor(NodeExporterTool)

        mock_shutil_which(monkeypatch)

        ir = tool.install()

        assert ir.returncode == 1, "node_exporter tool not found"
        assert tool.args is None

        mock_shutil_which(monkeypatch, ["node_exporter"])

        ir = tool.install()

        assert ir.returncode == 0, "node_exporter tool properly installed"
        assert tool.args == ["/usr/bin/node_exporter"]

    @staticmethod
    def test_install_pcp(monkeypatch):
        mocked_install_dir, _, tool = __class__.tool_constructor(PcpTool)

        mock_shutil_which(monkeypatch)

        ir = tool.install()

        assert ir.returncode == 1, "pcp tool (pmcd) not found"
        assert tool.args is None

        mock_shutil_which(monkeypatch, ["pmcd"])

        ir = tool.install()

        assert ir.returncode == 0, "pcp tool (pmcd) properly installed"
        assert tool.args == [
            "/usr/bin/pmcd",
            "--foreground",
            "--socket=./pmcd.socket",
            "--port=55677",
            f"--config={mocked_install_dir}/templates/pmcd.conf",
        ]

    @staticmethod
    def test_start(caplog):
        _, _, tool = __class__.tool_constructor(
            PersistentTool, "TestPersistentTool.test_start"
        )
        tool.args = ["/usr/bin/tool"]
        tool._create_process_with_logger = mocked_create_process_with_logger

        with pytest.raises(ToolException) as excinfo:
            tool.start(MockedPath(exists=False))
        assert str(excinfo.value) == "tool directory does not exist: '/foo/bar'"

        the_tool_dir = MockedPath()
        tool.start(the_tool_dir)
        assert tool.process.args == tool.args
        assert tool.process.tool_dir == the_tool_dir / "test-tool"
        assert tool.process.ctx_name == "start"
        assert len(caplog.record_tuples) == 2
        assert caplog.record_tuples[0][1] == logging.DEBUG
        assert (
            caplog.record_tuples[0][2]
            == "Starting persistent tool test-tool, args ['/usr/bin/tool']"
        )
        assert caplog.record_tuples[1][1] == logging.INFO
        assert (
            caplog.record_tuples[1][2]
            == "Started persistent tool test-tool, ['/usr/bin/tool']"
        )

    @staticmethod
    def test_stop(caplog):
        _, _, tool = __class__.tool_constructor(
            PersistentTool, "TestPersistentTool.test_stop"
        )
        tool.args = ["/usr/bin/tool"]

        tool.process = MockProcessForTerminate()
        tool.stop()

        assert tool.process.terminate_called is True
        assert len(caplog.record_tuples) == 1
        assert caplog.record_tuples[0][1] == logging.INFO
        assert (
            caplog.record_tuples[0][2]
            == "Terminate issued for persistent tool test-tool"
        )

    @staticmethod
    def test_stop_terminate_exeception(caplog):
        _, _, tool = __class__.tool_constructor(
            PersistentTool, "TestPersistentTool.test_stop_terminate_exeception"
        )
        tool.args = ["/usr/bin/tool"]
        tool.process = MockProcessForTerminate(raise_exc=True)
        tool.stop()

        assert tool.process.terminate_called is True
        assert len(caplog.record_tuples) == 1
        assert caplog.record_tuples[0][1] == logging.ERROR
        assert (
            caplog.record_tuples[0][2]
            == "Failed to terminate test-tool (['/usr/bin/tool'])"
        )

    @staticmethod
    def test_wait():
        _, _, tool = __class__.tool_constructor(PersistentTool)

        with pytest.raises(AssertionError):
            tool.wait()

        processes = []

        def mocked_wait_for_process_with_kill(process: str, ctx_name: str = None):
            nonlocal processes
            processes.append((process, ctx_name))

        tool.process = the_process = NullObject()
        tool._wait_for_process_with_kill = mocked_wait_for_process_with_kill

        tool.wait()

        assert len(processes) == 1
        assert processes[0][0] is the_process
        assert processes[0][1] is None


tar_file = "test.tar.xz"
tmp_dir = Path("nonexistent/tmp/dir")
tm_params = {
    "benchmark_run_dir": "",
    "channel_prefix": "",
    "tds_hostname": "test.hostname.com",
    "tds_port": 4242,
    "controller": "test.hostname.com",
    "group": "",
    "hostname": "test.hostname.com",
    "label": None,
    "tool_metadata": {"persistent": {}, "transient": {}},
    "tools": [],
}


@pytest.fixture
def tool_meister():
    return ToolMeister(
        pbench_install_dir=MockedPath(),
        tmp_dir=MockedPath(),
        tar_path="tar_path",
        sysinfo_dump=None,
        params=tm_params,
        redis_server=None,
        logger=logging.getLogger(),
    )


class TestCreateTar:
    """Test the ToolMeister._create_tar() method behaviors."""

    @staticmethod
    def test_create_tar(tool_meister, monkeypatch):
        """Test create tar file"""

        def mock_run(*args, **kwargs):
            assert kwargs["cwd"] == tmp_dir.parent
            assert kwargs["stdin"] is None
            assert kwargs["stderr"] == subprocess.STDOUT
            assert kwargs["stdout"] == subprocess.PIPE
            c = subprocess.CompletedProcess(args, returncode=0, stdout=b"", stderr=None)
            assert all(
                x in c.args[0]
                for x in [
                    "tar_path",
                    "--create",
                    "--xz",
                    "--force-local",
                    f"--file={tar_file}",
                ]
            )
            return c

        monkeypatch.setattr(subprocess, "run", mock_run)

        cp = tool_meister._create_tar(tmp_dir, Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == b""

    @staticmethod
    def test_create_tar_ignore_warnings(tool_meister, monkeypatch):
        """Test creating tar with warning=none option specified"""

        expected_std_out = b"No error after --warning=none"

        def mock_run(*args, **kwargs):
            if "--warning=none" in args[0]:
                return subprocess.CompletedProcess(
                    args,
                    returncode=0,
                    stdout=expected_std_out,
                    stderr=None,
                )
            else:
                return subprocess.CompletedProcess(
                    args, returncode=1, stdout=b"Some error running tar", stderr=None
                )

        monkeypatch.setattr(subprocess, "run", mock_run)

        cp = tool_meister._create_tar(tmp_dir, Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == expected_std_out

    @staticmethod
    def test_create_tar_failure(tool_meister, monkeypatch, caplog):
        """Test tar creation failure"""

        # Record number of times mock functions called by this test
        functions_called = []

        expected_std_out = b"Some error running tar command, empty tar creation failed"

        def mock_run(*args, **kwargs):
            functions_called.append("mock_run")
            return subprocess.CompletedProcess(
                args,
                returncode=1,
                stdout=expected_std_out,
                stderr=None,
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        cp = tool_meister._create_tar(tmp_dir, Path(tar_file))
        assert cp.returncode == 1
        assert cp.stdout == expected_std_out
        assert functions_called == ["mock_run", "mock_run"]


class TestSendDirectory:
    """Test ToolMeister._send_directory()"""

    directory = tmp_dir / f"{tm_params['hostname']}"

    @staticmethod
    def mock_create_tar(returncode: int, stdout: bytes, functions_called: list):
        def f(directory: Path, tar_file: Path):
            functions_called.append("mock_create_tar")
            return subprocess.CompletedProcess(
                args=[], returncode=returncode, stdout=stdout, stderr=None
            )

        return f

    @responses.activate
    def test_tar_create_success(self, tool_meister, monkeypatch):
        """This test should pass the tar creation in send directory"""

        # Record all the mock functions called by this test
        functions_called = []

        def mock_unlink(*args):
            assert args[0] == Path(f"{self.directory}.tar.xz")
            functions_called.append("mock_unlink")

        def mock_open(*args):
            assert args[0] == Path(f"{self.directory}.tar.xz")
            functions_called.append("mock_open")
            return io.StringIO()

        def mock_rmtree(directory: Path):
            assert directory == tmp_dir
            functions_called.append("mock_rmtree")

        def mock_md5(tar_file: Path):
            assert tar_file == Path(f"{self.directory}.tar.xz")
            functions_called.append("mock_md5")
            return 10, "random_md5"

        monkeypatch.setattr(shutil, "rmtree", mock_rmtree)
        monkeypatch.setattr("pbench.agent.tool_meister.md5sum", mock_md5)
        monkeypatch.setattr(Path, "unlink", mock_unlink)
        monkeypatch.setattr(Path, "open", mock_open)

        monkeypatch.setattr(
            tool_meister, "_create_tar", self.mock_create_tar(0, b"", functions_called)
        )

        url = (
            f"http://{tm_params['tds_hostname']}:{tm_params['tds_port']}/uri"
            f"/ctx/{tm_params['hostname']}"
        )
        responses.add(responses.PUT, url, status=HTTPStatus.OK, body="succeeded")

        failures = tool_meister._send_directory(self.directory, "uri", "ctx")
        assert functions_called == [
            "mock_create_tar",
            "mock_md5",
            "mock_open",
            "mock_rmtree",
            "mock_unlink",
        ]
        assert failures == 0

    def test_tar_create_failure(self, tool_meister, monkeypatch):
        """Check if the tar creation error is properly captured in send_directory"""

        # Record all the mock functions called by this test
        functions_called = []

        def mock_unlink(*args):
            assert args[0] == Path(f"{self.directory}.tar.xz")
            functions_called.append("mock_unlink")

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        monkeypatch.setattr(
            tool_meister,
            "_create_tar",
            self.mock_create_tar(1, b"Error in tarball creation", functions_called),
        )

        with pytest.raises(ToolMeisterError) as exc:
            tool_meister._send_directory(self.directory, "uri", "ctx")

        assert functions_called == ["mock_create_tar", "mock_create_tar", "mock_unlink"]
        assert f"Failed to create an empty tar {self.directory}.tar.xz" in str(
            exc.value
        )
