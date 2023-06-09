import pytest

EMPTY = b""
USAGE = b"Usage: pbench-list-tools [OPTIONS]"
TRACEBACK = b"Traceback (most recent call last):\n"

BAD_GROUP_ERR = b"Bad tool group: "
TOOL_ERR = b'Tool "unknown" not found in '
NO_TOOL_GROUP = b"No tool groups found"


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
        assert NO_TOOL_GROUP in err
        assert EMPTY == out
        assert exitcode == 0

    def test_name(self, agent_config):
        command = ["pbench-list-tools", "--name", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TOOL_ERR + b"any group" in err
        assert EMPTY == out
        assert exitcode == 1

    def test_group(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert BAD_GROUP_ERR in err
        assert EMPTY == out
        assert exitcode == 1

    def test_group_name(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo", "--name", "iostat"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert BAD_GROUP_ERR in err
        assert EMPTY == out
        assert exitcode == 1

    def test_group_options(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert BAD_GROUP_ERR in err
        assert EMPTY == out
        assert exitcode == 1

    def test_group_name_options(self, agent_config):
        command = [
            "pbench-list-tools",
            "--group",
            "foo",
            "--name",
            "iostat",
            "--with-option",
        ]
        out, err, exitcode = pytest.helpers.capture(command)
        assert BAD_GROUP_ERR in err
        assert EMPTY == out
        assert exitcode == 1

    def test_option(self, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert NO_TOOL_GROUP in err
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

    @pytest.fixture
    def tools_on_multiple_hosts(self, pbench_run):
        p = pbench_run / "tools-v1-default" / "testhost.example.com"
        p.mkdir(parents=True)
        for tool in ["perf", "mpstat", "sar"]:
            (p / tool).touch()
        p = pbench_run / "tools-v1-default" / "testhost2.example.com"
        p.mkdir(parents=True)
        for tool in ["iostat", "proc-vmstat", "sar"]:
            (p / tool).touch()

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
        assert b"group: default; host: testhost.example.com; tools: perf\n" == out
        assert exitcode == 0

    def test_name(self, tool, agent_config):
        command = ["pbench-list-tools", "-n", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err
        assert b"group: default; host: testhost.example.com; tools: perf\n" == out
        assert exitcode == 0

    # Issue #2345
    def test_name_with_random_file(self, tool_with_random_file, agent_config):
        command = ["pbench-list-tools", "-n", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err and exitcode == 0
        assert b"group: default; host: testhost.example.com; tools: perf\n" == out

    # Issue #2302
    def test_unknown_group(self, tool, agent_config):
        command = ["pbench-list-tools", "-g", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert BAD_GROUP_ERR in err and exitcode == 1
        assert EMPTY == out

    def test_group_existing(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert EMPTY == err and exitcode == 0
        assert b"group: default; host: testhost.example.com; tools: perf\n" == out

    def test_name_existing(self, tool, agent_config):
        command = ["pbench-list-tools", "-n", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert EMPTY == err and exitcode == 0
        assert b"group: default; host: testhost.example.com; tools: perf\n" == out

    def test_non_existent_group(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert BAD_GROUP_ERR in err and exitcode == 1
        assert EMPTY == out

    def test_non_existent_name(self, tool, agent_config):
        command = ["pbench-list-tools", "-n", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TOOL_ERR + b"any group" in err and exitcode == 1
        assert EMPTY == out

    def test_existing_group_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default", "--name", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert EMPTY == err and exitcode == 0
        assert b"group: default; host: testhost.example.com; tools: perf\n" == out

    def test_existing_group_non_existent_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default", "--name", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TOOL_ERR + b"default" in err and exitcode == 1
        assert EMPTY == out

    def test_non_existent_group_existing_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "unknown", "--name", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert BAD_GROUP_ERR in err and exitcode == 1
        assert EMPTY == out

    def test_multiple_hosts(self, tools_on_multiple_hosts, agent_config):
        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert EMPTY == err and exitcode == 0
        assert (
            b"group: default; host: testhost.example.com; tools: mpstat, perf, sar\n"
            b"group: default; host: testhost2.example.com; tools: iostat, proc-vmstat, sar\n"
            == out
        )

    def test_no_tools_found(self, pbench_run, agent_config):
        p = pbench_run / "tools-v1-default"
        p.mkdir(parents=True)

        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 0
        assert EMPTY == out
        assert b"No tools found\n" == err

    def test_no_tools_found_in_group(self, pbench_run, agent_config):
        p = pbench_run / "tools-v1-default"
        p.mkdir(parents=True)

        command = ["pbench-list-tools", "--group", "default"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 0
        assert EMPTY == out
        assert b'No tools found in group "default"' in err


class Test_list_tools_tools_registered_with_options:
    @pytest.fixture
    def single_group_tools(self, pbench_run):
        p = pbench_run / "tools-v1-default" / "testhost.example.com"
        p.mkdir(parents=True)
        tool = p / "iostat"
        tool.write_text("--interval=30")
        tool = p / "mpstat"
        tool.write_text("--interval=300")

    @pytest.fixture
    def multiple_group_tools(self, pbench_run):
        for group in ["default", "test"]:
            p = pbench_run / f"tools-v1-{group}" / "testhost.example.com"
            p.mkdir(parents=True)
            tool = p / "iostat"
            tool.write_text("--interval=30")
            tool = p / "mpstat"
            tool.write_text("--interval=300")
            if group == "default":
                tool = p / "sar"
                tool.write_text("--interval=10")
            else:
                tool = p / "perf"
                tool.write_text("--record-opts='-a --freq=100'")

    @pytest.fixture
    def tools_on_multiple_hosts(self, pbench_run):
        for group in ["default", "test"]:
            for host in ["th1.example.com", "th2.example.com"]:
                p = pbench_run / f"tools-v1-{group}" / host
                p.mkdir(parents=True)
                tool = p / "iostat"
                tool.write_text("--interval=30")
                tool = p / "mpstat"
                tool.write_text("--interval=300")
                if host == "th1.example.com":
                    tool = p / "sar"
                    tool.write_text("--interval=10")
                else:
                    tool = p / "perf"
                    tool.write_text("--record-opts='-a --freq=100'")

    # Issue #3454
    @pytest.fixture
    def labels_on_multiple_hosts(self, pbench_run, tools_on_multiple_hosts):
        # This fixture is meant to be called after the previous one
        # (tools_on_multiple_hosts). The previous one establishes a
        # tool-like directory structure; this one just embellishes it
        # with labels on some host entries. Think of it as a
        # double for-loop, like the one above, only unrolled.

        # row 1
        group = "default"

        # column 1
        host = "th1.example.com"
        label = pbench_run / f"tools-v1-{group}" / host / "__label__"
        label.write_text("foo")

        # column 2
        host = "th2.example.com"
        label = pbench_run / f"tools-v1-{group}" / host / "__label__"
        label.write_text("bar")

        # row 2
        group = "test"

        # column 1
        host = "th1.example.com"
        label = pbench_run / f"tools-v1-{group}" / host / "__label__"
        label.write_text("bar")

        # column 2
        # th2 has no label

    # Issue #2346
    def test_existing_group_options(self, single_group_tools, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert TRACEBACK not in err
        assert EMPTY == err and exitcode == 0
        assert (
            b"group: default; host: testhost.example.com; tools: iostat --interval=30, mpstat --interval=300"
            in out
        )

    def test_non_existent_group_options(self, multiple_group_tools, agent_config):
        command = ["pbench-list-tools", "--group", "unknown", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert BAD_GROUP_ERR in err and exitcode == 1
        assert EMPTY == out

    def test_existing_group_name_options(self, multiple_group_tools, agent_config):
        command = [
            "pbench-list-tools",
            "--group",
            "default",
            "--name",
            "mpstat",
            "--with-option",
        ]
        out, err, exitcode = pytest.helpers.capture(command)
        assert EMPTY == err and exitcode == 0
        assert (
            b"group: default; host: testhost.example.com; tools: mpstat --interval=300"
            in out
        )

    def test_option(self, multiple_group_tools, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert EMPTY == err and exitcode == 0
        assert (
            b"group: default; host: testhost.example.com; tools: iostat --interval=30, mpstat --interval=300, sar --interval=10\ngroup: test; host: testhost.example.com; tools: iostat --interval=30, mpstat --interval=300, perf --record-opts='-a --freq=100'"
            in out
        )

    def test_multiple_hosts_with_options(self, tools_on_multiple_hosts, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert EMPTY == err and exitcode == 0
        assert (
            b"group: default; host: th1.example.com; tools: iostat --interval=30, mpstat --interval=300, sar --interval=10\ngroup: default; host: th2.example.com; tools: iostat --interval=30, mpstat --interval=300, perf --record-opts='-a --freq=100'\ngroup: test; host: th1.example.com; tools: iostat --interval=30, mpstat --interval=300, sar --interval=10\ngroup: test; host: th2.example.com; tools: iostat --interval=30, mpstat --interval=300, perf --record-opts='-a --freq=100'"
            in out
        )

    def test_multiple_hosts_with_labels(self, labels_on_multiple_hosts, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert EMPTY == err and exitcode == 0
        assert (
            b"group: default; host: th1.example.com, label: foo; tools: iostat --interval=30, mpstat --interval=300, sar --interval=10\ngroup: default; host: th2.example.com, label: bar; tools: iostat --interval=30, mpstat --interval=300, perf --record-opts='-a --freq=100'\ngroup: test; host: th1.example.com, label: bar; tools: iostat --interval=30, mpstat --interval=300, sar --interval=10\ngroup: test; host: th2.example.com; tools: iostat --interval=30, mpstat --interval=300, perf --record-opts='-a --freq=100'"
            in out
        )
