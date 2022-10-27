import pathlib
import sys
from typing import Any, Callable, Iterable, List, Optional, Tuple, TypeVar
from unittest.mock import MagicMock

from click.testing import CliRunner
import psutil

from pbench.agent.tool_group import ToolGroup
from pbench.cli.agent.commands.tools import kill


def ourecho(msg: str, err: bool = False):
    """Simplistic mock of click.echo."""
    print(msg, file=(sys.stderr if err else sys.stdout))


AP = TypeVar("AP", bound="AnotherPath")


class AnotherPath:
    """Another "Path" implementation to help unit tests mock the behavior of
    Path based on the contents of the name argument given in the constructor.
    """

    def __init__(self, name: str, val: Optional[str] = None):
        """Approximate mocked behavior of a Path object where an actual Path
        object is used to provide the `name` and `parts` fields.
        """
        p = pathlib.Path(name)
        self._str = str(p)
        self.parts = p.parts
        self.name = p.name
        if not p.name:
            self.parent = self
        else:
            self.parent = AnotherPath(str(p.parent))
        self.val = val

    def is_dir(self) -> bool:
        """A directory is determined by its suffix NOT being in a known list."""
        return not self.name.endswith((".uuid", ".pid", ".file"))

    def read_text(self) -> str:
        """The read text value is returned using the value that was provided
        when the mocked object was created, otherwise a FileNotFoundError is
        raised.
        """
        if self.val is None:
            raise FileNotFoundError(self.name)
        return self.val

    def __truediv__(self, arg: str) -> AP:
        """Create a new instance of this object with argument added to the
        path.
        """
        return AnotherPath(f"{self._str}/{arg}", val=self.val)

    def __str__(self) -> str:
        return self._str


class MyProcess:
    """Very simple psutil.Process object mock which only has a `pid` attribute."""

    def __init__(self, pid: str):
        self.pid = int(pid)


class TestPidSource:
    @staticmethod
    def test_load_fnf():
        mydir = AnotherPath("fake_dir")
        ps = kill.PidSource("that.pid", "display that")
        assert ps.load(mydir, "uuid1") is False

    @staticmethod
    def test_load_nsp(monkeypatch):
        class MyNoSuchProcess:
            def __init__(self, pid: int):
                raise psutil.NoSuchProcess(pid)

        mydir = AnotherPath("fake_dir", "12345")
        ps = kill.PidSource("that.pid", "display that")
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.psutil.Process", MyNoSuchProcess
        )
        assert ps.load(mydir, "uuid1") is False

    @staticmethod
    def test_load_found(monkeypatch):
        mydir = AnotherPath("fake_dir", "67890")
        ps = kill.PidSource("that.pid", "display that")
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.psutil.Process", MyProcess
        )
        assert ps.load(mydir, "uuid1") is True

    @staticmethod
    def test_noop_killem(monkeypatch, capsys):
        mock_kf = MagicMock()
        monkeypatch.setattr(kill, "kill_family", mock_kf)
        ps = kill.PidSource("this.pid", "display this")
        ps.killem(ourecho)
        assert not mock_kf.called
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    @staticmethod
    def test_killem_raises_exception(monkeypatch, capsys):
        mock_kf = MagicMock(side_effect=Exception("exception"))
        monkeypatch.setattr(kill, "kill_family", mock_kf)
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.psutil.Process", MyProcess
        )
        ps = kill.PidSource("this.pid", "display this")
        ps.load(AnotherPath("fake_dir1", "123"), "uuid1")
        ps.killem(ourecho)
        captured = capsys.readouterr()
        assert (
            captured.out
            == "Killing display this PIDs ...\n\tKilling 123 (from fake_dir1)\n"
        )
        assert captured.err == "\t\terror killing 123: exception\n"

    @staticmethod
    def test_killem(monkeypatch, capsys):
        mock_kf = MagicMock()
        monkeypatch.setattr(kill, "kill_family", mock_kf)
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.psutil.Process", MyProcess
        )
        ps = kill.PidSource("this.pid", "display this")
        pid_data = {
            "uuid1": {"dirname": "fake_dir1", "pid": "123"},
            "uuid2": {"dirname": "fake_dir2", "pid": "456"},
            "uuid3": {"dirname": "fake_dir3", "pid": "789"},
        }
        for uuid, vals in pid_data.items():
            ps.load(AnotherPath(vals["dirname"], vals["pid"]), uuid)
        ps.killem(ourecho)
        assert len(mock_kf.mock_calls) == len(pid_data)
        for idx, uuid in enumerate(pid_data.keys()):
            assert mock_kf.mock_calls[idx][1][0].pid == int(pid_data[uuid]["pid"])
        # Verify a second call to killem() is a no-op.
        mock_kf.reset_mock()
        ps.killem(ourecho)
        mock_kf.assert_not_called()
        captured = capsys.readouterr()
        expected_output = "Killing display this PIDs ...\n"
        for uuid, vals in pid_data.items():
            expected_output += f"\tKilling {vals['pid']} (from {vals['dirname']})\n"
        assert captured.out == expected_output
        assert captured.err == ""


class TestKillTools:
    @staticmethod
    def test_gen_result_tm_directories():
        class FakePbenchRun:
            """A very specific mock for a pbench_run Path object where we
            leverage the AnotherPath class to yield a series of AnotherPath
            objects which respond as directories, passing along the value to
            be read from a file they contain.
            """

            def __init__(self, dir_pairs: List[Tuple[str, str]]):
                self.dir_names = dir_pairs

            def iterdir(self):
                for name, val in self.dir_names:
                    yield AnotherPath(name, val)

        pr = FakePbenchRun(
            [
                ("abc.file", None),  # top level file
                ("filenotf", None),  # directory with no .uuid file
                ("res1", "abcdef"),  # directory with a file
                ("res2", "ghijkl"),  # directory with a file
            ]
        )
        pairs = list(kill.gen_result_tm_directories(pr))
        assert (
            pairs[0][0].parent.name == "res1"
            and pairs[0][0].name == "tm"
            and pairs[0][1] == "abcdef"
        )
        assert (
            pairs[1][0].parent.name == "res2"
            and pairs[1][0].name == "tm"
            and pairs[1][1] == "ghijkl"
        )

    @staticmethod
    def test_gen_host_names_no_tool_groups(monkeypatch):
        """Verify kill.gen_host_names() is a no-op when we have no tool groups
        present.
        """

        def mock_gen_tool_groups(pbench_run: str) -> Iterable[ToolGroup]:
            """Override kill.gen_tool_groups definition to yield no ToolGroup
            objects.
            """
            for group in []:
                yield ToolGroup(group)

        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.gen_tool_groups", mock_gen_tool_groups
        )
        assert not any(kill.gen_host_names(pathlib.Path("no-tool-group-dirs")))

    @staticmethod
    def test_gen_host_names(monkeypatch):
        """Verify kill.gen_host_names() yields the expected list of hosts from
        the discovered ToolGroups.
        """

        class MockToolGroup:
            """A simplified tool group object which only provides the
            `hostnames` dictionary.
            """

            def __init__(self, hosts: List[str]):
                self.hostnames = {}
                for host in hosts:
                    self.hostnames[host] = None

        tool_group_host_names = [
            ["localhost.example.com"],
            ["localhost.example.com", "remote1.example.com"],
            ["remote2.example.com", "remote3.example.com"],
        ]
        expected_hosts = {
            "remote1.example.com",
            "remote2.example.com",
            "remote3.example.com",
        }

        def mock_gen_tool_groups(pbench_run: str) -> Iterable[MockToolGroup]:
            """Override kill.gen_tool_groups definition to return a simple
            tool group object.
            """
            for hosts in tool_group_host_names:
                yield MockToolGroup(hosts)

        class MockLocalRemoteHost:
            """A simple mock for the LocalRemoteHost behaviors."""

            def is_local(self, host_name: str):
                return host_name.startswith("localhost")

        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.gen_tool_groups", mock_gen_tool_groups
        )
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.LocalRemoteHost", MockLocalRemoteHost
        )

        hosts = set(kill.gen_host_names(pathlib.Path("have-tool-group-dirs")))
        assert hosts == expected_hosts

    @staticmethod
    def test_with_uuids(monkeypatch):
        """Verify UUID arguments work correctly.

        The scenario we construct artificially starts with an invocation using
        3 UUIDs, one won't be found.  The mocked-out `psutil.process_iter()`
        will generate 3 PIDs, one of which will have child processes, which
        will all operate normally with no exceptions.  Of the other two, one
        will raise an exception, and the other will not be found.
        """
        action_list = []
        uuid_list = ("uuid1abc", "uuid2def", "uuid3ghi")

        MP = TypeVar("MP", bound="MockProcess")  # noqa F821

        class MockProcess:
            """Behavior mock for the `psutil.Process` class."""

            def __init__(
                self,
                pid: int,
                uuid: Optional[str] = None,
                children: Optional[List[Any]] = None,
                do: Optional[str] = None,
            ):
                self.pid = pid
                self._uuid = uuid
                self._children = [] if children is None else children
                self._do = do

            def children(self, recursive: Optional[bool] = False) -> Iterable[MP]:
                assert recursive
                for child in self._children:
                    yield child

            def cmdline(self) -> List[str]:
                return [
                    "arg0",
                    "arg1",
                    "arg2" if not self._uuid else self._uuid,
                    "arg3",
                ]

            def kill(self):
                if self._do == "nosuch":
                    action_list.append(("kill-nosuch", self.pid, self._uuid))
                    raise psutil.NoSuchProcess(self.pid)
                if self._do == "exc":
                    action_list.append(("kill-except", self.pid, self._uuid))
                    raise Exception("generic exception")
                action_list.append(("kill", self.pid, self._uuid))

        class mock_psutil:
            """Even though the target `psutil` is a module, we just use a
            class with a static method to duck-type it.
            """

            class NoSuchProcess(Exception):
                pass

            @staticmethod
            def process_iter():
                # First pid has 3 children
                yield MockProcess(
                    12345,
                    uuid=uuid_list[0],
                    children=[
                        MockProcess(12346),
                        MockProcess(12347),
                        MockProcess(12348, do="nosuch"),
                    ],
                )
                yield MockProcess(23456)
                yield MockProcess(34567, uuid=uuid_list[1], do="exc")
                yield MockProcess(45678, uuid=uuid_list[2], do="nosuch")

        runner = CliRunner(mix_stderr=False)
        monkeypatch.setattr("pbench.cli.agent.commands.tools.kill.psutil", mock_psutil)
        result = runner.invoke(kill.main, list(uuid_list))
        assert result.exit_code == 0
        expected_action_list = [
            ("kill", 12345, uuid_list[0]),
            ("kill", 12346, None),
            ("kill", 12347, None),
            ("kill-nosuch", 12348, None),
            ("kill-except", 34567, uuid_list[1]),
            ("kill-nosuch", 45678, uuid_list[2]),
        ]
        assert action_list == expected_action_list, (
            f"action_list={action_list!r},"
            f" expected_action_list={expected_action_list!r},"
            f" stdout={result.stdout!r},"
            f" stderr={result.stderr!r}"
        )

    @staticmethod
    def test_without_uuids_no_action(monkeypatch):
        """Exercise the code path where no result directories are found, so
        there is nothing to kill.
        """

        def mock_gen_result_tm_directories(
            run_dir: pathlib.Path,
        ) -> Iterable[Tuple[pathlib.Path, str]]:
            """Intentional generator which does not yield anything."""
            for run_dir in []:
                yield run_dir, "uuid"

        runner = CliRunner(mix_stderr=False)
        monkeypatch.setattr("pbench.cli.agent.commands.tools.kill.PidSource", MagicMock)
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.gen_result_tm_directories",
            mock_gen_result_tm_directories,
        )
        result = runner.invoke(kill.main)
        assert (
            result.exit_code == 0
        ), f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        assert (
            result.stdout == ""
        ), f"stdout={result.stdout!r}, stderr={result.stderr!r}"

    @staticmethod
    def test_without_uuids_with_action(monkeypatch):
        """Exercise the code paths for both local and remote PIDs to kill.

        Since the PidSource object is mocked out, we just care that the
        .load() and .killem() methods are invoked for all three PID sources.

        For the remotes we just need to have a few remote hosts generated, one
        with a single UUID, and another with multiple UUIDs.  We just care
        that expected TemplateSsh object's .start() and .wait() methods are
        called for the given hosts.
        """
        action_list = []

        class MockPidSource:
            """No-op mock for PidSource."""

            def __init__(self, file_name: str, display_name: str):
                self.file_name = file_name
                self.display_name = display_name

            def load(self, tm_dir: pathlib.Path, uuid: str) -> bool:
                action_list.append(("load", self.file_name, str(tm_dir), uuid))
                return True

            def killem(self, echo: Callable[[str], None]) -> None:
                action_list.append(("killem", self.display_name))

        def mock_gen_result_tm_directories(
            pbench_run_dir: pathlib.Path,
        ) -> Iterable[Tuple[pathlib.Path, str]]:
            for tm_dir in [
                (pathlib.Path("res0/tm"), "uuid1abc"),
                (pathlib.Path("res1/tm"), "uuid2def"),
                (pathlib.Path("res2/tm"), "uuid3ghi"),
            ]:
                yield tm_dir

        def mock_gen_host_names(res_dir: pathlib.Path) -> str:
            hosts = {"res0": ["hostA", "hostB"], "res2": ["host3"]}
            for host in hosts.get(res_dir.name, []):
                yield host

        class MockTemplateSsh:
            def __init__(self, name: str, ssh_opts: List[str], cmd: str):
                self.name = name
                self.ssh_opts = ssh_opts
                self.cmd = cmd

            def start(self, host: str, **kwargs):
                action_list.append(("start", host, repr(kwargs)))

            def wait(self, host: str):
                action_list.append(("wait", host))

        runner = CliRunner(mix_stderr=False)
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.PidSource", MockPidSource
        )
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.gen_result_tm_directories",
            mock_gen_result_tm_directories,
        )
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.gen_host_names",
            mock_gen_host_names,
        )
        monkeypatch.setattr(
            "pbench.cli.agent.commands.tools.kill.TemplateSsh",
            MockTemplateSsh,
        )
        result = runner.invoke(kill.main, catch_exceptions=False)
        assert (
            result.exit_code == 0
        ), f"stdout={result.stdout!r}, stderr={result.stderr!r}"
        expected_action_list = [
            ("load", "redis.pid", "res0/tm", "uuid1abc"),
            ("load", "pbench-tool-data-sink.pid", "res0/tm", "uuid1abc"),
            ("load", "tm.pid", "res0/tm", "uuid1abc"),
            ("load", "redis.pid", "res1/tm", "uuid2def"),
            ("load", "pbench-tool-data-sink.pid", "res1/tm", "uuid2def"),
            ("load", "tm.pid", "res1/tm", "uuid2def"),
            ("load", "redis.pid", "res2/tm", "uuid3ghi"),
            ("load", "pbench-tool-data-sink.pid", "res2/tm", "uuid3ghi"),
            ("load", "tm.pid", "res2/tm", "uuid3ghi"),
            ("killem", "redis server"),
            ("killem", "tool data sink"),
            ("killem", "local tool meister"),
            ("start", "hostA", "{'uuids': 'uuid1abc'}"),
            ("start", "hostB", "{'uuids': 'uuid1abc'}"),
            ("start", "host3", "{'uuids': 'uuid3ghi'}"),
            ("wait", "hostA"),
            ("wait", "hostB"),
            ("wait", "host3"),
        ]
        assert action_list == expected_action_list, (
            f"action_list={action_list!r},"
            f" stdout={result.stdout!r},"
            f" stderr={result.stderr!r}"
        )
        expected_stdout = """Killing all Tool Meister processes on remote host hostA...
Killing all Tool Meister processes on remote host hostB...
Killing all Tool Meister processes on remote host host3...
"""
        assert result.stdout == expected_stdout, (
            f"action_list={action_list!r},"
            f" stdout={result.stdout!r},"
            f" stderr={result.stderr!r}"
        )

    @staticmethod
    def test_help():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(kill.main, ["--help"])
        assert result.exit_code == 0
        assert str(result.stdout).startswith("Usage:")
        assert not result.stderr_bytes
