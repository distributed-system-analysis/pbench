import pytest

group_err = b"Tool group does not exist: "
tool_err = b"Tool does not exist in any group: "
usage_msg = b"Usage: pbench-list-tools [OPTIONS]"


class Test_list_tool_no_tools_registered:
    def test_help(self):
        command = ["pbench-list-tools", "--help"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"Usage: pbench-list-tools [OPTIONS]" in out
        assert exitcode == 0

    def test_no_args(self, agent_config):
        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert b"" == out
        assert exitcode == 0

    def test_name(self, agent_config):
        command = ["pbench-list-tools", "--name", "foo"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert tool_err in err
        assert exitcode == 1

    def test_group(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert group_err in err
        assert exitcode == 1

    def test_group_name(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo", "--name", "iostat"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert group_err in err
        assert exitcode == 1

    def test_group_options(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert group_err in err
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
        assert b"" == out
        assert group_err in err
        assert exitcode == 1

    def test_option(self, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert b"" == err
        assert exitcode == 0


class Test_list_tool_tools_registered:
    @pytest.fixture
    def tool(self, pbench_run):
        p = pbench_run / "tools-v1-default" / "testhost.example.com"
        p.mkdir(parents=True)
        tool = p / "perf"
        tool.touch()

    @pytest.fixture
    def tools_on_multiple_hosts(self, pbench_run):
        p = pbench_run / "tools-v1-default" / "testhost.example.com"
        p.mkdir(parents=True)
        for tool in ["perf", "mpstat"]:
            (p / tool).touch()
        p = pbench_run / "tools-v1-default" / "testhost2.example.com"
        p.mkdir(parents=True)
        for tool in ["iostat", "sar"]:
            (p / tool).touch()

    def test_help(self, tool, agent_config):
        command = ["pbench-list-tools", "--help"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert usage_msg in out
        assert b"" == err
        assert exitcode == 0

    def test_no_args(self, tool, agent_config):
        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"default: testhost.example.com: perf\n" == out
        assert exitcode == 0

    def test_group_existing(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"default: testhost.example.com: perf\n" == out
        assert b"" == err
        assert exitcode == 0

    def test_name_existing(self, tool, agent_config):
        command = ["pbench-list-tools", "-n", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"tool name: perf groups: default\n" == out
        assert b"" == err
        assert exitcode == 0

    def test_non_existent_group(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert group_err in err
        assert exitcode == 1

    def test_non_existent_name(self, tool, agent_config):
        command = ["pbench-list-tools", "-n", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert tool_err in err
        assert exitcode == 1

    def test_existing_group_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default", "--name", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"tool name: perf groups: default\n" == out
        assert b"" == err
        assert exitcode == 0

    def test_existing_group_non_existent_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default", "--name", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert tool_err in err
        assert exitcode == 1

    def test_non_existent_group_existing_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "unknown", "--name", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert group_err in err
        assert exitcode == 1

    def test_multiple_hosts(self, tools_on_multiple_hosts, agent_config):
        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)

        assert (
            b"default: testhost.example.com: mpstat,perf\ndefault: testhost2.example.com: iostat,sar\n"
            == out
        )
        assert b"" == err
        assert exitcode == 0


class Test_list_tool_tools_registered_with_options:
    @pytest.fixture
    def tool(self, pbench_run):
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

    def test_existing_group_options(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        # This is (apart from the hostname) the 0.69.9 output.
        assert (
            b"default: testhost.example.com: iostat --interval=30,mpstat --interval=300,sar --interval=10\n"
            == out
        )
        assert b"" == err
        assert exitcode == 0

    def test_non_existent_group_options(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "unknown", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert group_err in err
        assert exitcode == 1

    def test_existing_group_name_options(self, tool, agent_config):
        command = [
            "pbench-list-tools",
            "--group",
            "default",
            "--name",
            "mpstat",
            "--with-option",
        ]
        out, err, exitcode = pytest.helpers.capture(command)
        assert (
            b"tool name: mpstat\ngroup: default, host: testhost.example.com, options: --interval=300\n"
            == out
        )
        assert b"" == err
        assert exitcode == 0

    def test_option(self, tool, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        # This is the 0.69.9 output with hostname mods
        assert (
            b"default: testhost.example.com: iostat --interval=30,mpstat --interval=300,sar --interval=10\ntest: testhost.example.com: iostat --interval=30,mpstat --interval=300,perf --record-opts='-a --freq=100'\n"
            == out
        )
        assert b"" == err
        assert exitcode == 0

    def test_multiple_hosts_with_options(self, tools_on_multiple_hosts, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)

        import sys

        print(out, file=sys.stderr)
        # This is the 0.69.9 output with hostname mods
        assert (
            b"default: th1.example.com: iostat --interval=30,mpstat --interval=300,sar --interval=10\ndefault: th2.example.com: iostat --interval=30,mpstat --interval=300,perf --record-opts='-a --freq=100'\ntest: th1.example.com: iostat --interval=30,mpstat --interval=300,sar --interval=10\ntest: th2.example.com: iostat --interval=30,mpstat --interval=300,perf --record-opts='-a --freq=100'\n"
            == out
        )
        assert b"" == err
        assert exitcode == 0
