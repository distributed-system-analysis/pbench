import pytest


EMPTY = b""
USAGE = b"Usage: pbench-list-tools [OPTIONS]"
BAD_GROUP = b"Bad tool group: "
TRACEBACK = b"Traceback (most recent call last):\n"


class Test_list_tools_no_tools_registered:
    def test_help(self):
        command = ["pbench-list-tools", "--help"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err
        assert USAGE in out
        assert exitcode == 0

    def test_no_args(self, agent_config):
        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err
        assert EMPTY == out
        assert exitcode == 0


class Test_list_tools_tools_registered:
    @pytest.fixture
    def tool(self, pbench_run):
        p = pbench_run / "tools-v1-default" / "testhost.example.com"
        p.mkdir(parents=True)
        tool = p / "perf"
        tool.touch()

    @pytest.fixture
    def tool_with_random_file(self, pbench_run):
        p = pbench_run / "tools-v1-default" / "testhost.example.com"
        p.mkdir(parents=True)
        (p.parent / "foo").touch()
        tool = p / "perf"
        tool.touch()

    def test_help(self, tool, agent_config):
        command = ["pbench-list-tools", "--help"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err
        assert USAGE in out
        assert exitcode == 0

    def test_no_args(self, tool, agent_config):
        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err
        assert b"default: testhost.example.com ['perf']" in out
        assert exitcode == 0

    def test_name(self, tool, agent_config):
        command = ["pbench-list-tools", "-n", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err
        assert b"tool name: perf groups: default" in out
        assert exitcode == 0

    # Issue #2345
    def test_name_with_random_file(self, tool_with_random_file, agent_config):
        command = ["pbench-list-tools", "-n", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err and exitcode == 0
        assert b"tool name: perf groups: default" in out

    # Issue #2302
    def test_unknown_group(self, tool, agent_config):
        command = ["pbench-list-tools", "-g", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert BAD_GROUP in err
        assert EMPTY == out
        # this is 0.69.9 behavior
        assert exitcode == 0


class Test_list_tools_tools_registered_with_options:
    @pytest.fixture
    def single_group_tools(self, pbench_run):
        p = pbench_run / "tools-v1-default" / "testhost.example.com"
        p.mkdir(parents=True)
        tool = p / "iostat"
        tool.write_text("--interval=30")
        tool = p / "mpstat"
        tool.write_text("--interval=300")

    # Issue #2346
    def test_existing_group_options(self, single_group_tools, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err and exitcode == 0
        assert (
            b"default: testhost.example.com [('iostat', '--interval=30'), ('mpstat', '--interval=300')]\n"
            == out
        )
