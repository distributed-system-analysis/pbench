import pytest


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
        assert exitcode == 0

    def test_name(self, agent_config):
        command = ["pbench-list-tools", "--name", "foo"]
        out, err, exitcode = pytest.helpers.capture(command)
        # XXX 0.69.9 backward compatibility: non-existent names do no return errors
        assert exitcode == 0

    def test_group(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_group_name(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo", "--name", "iostat"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_group_options(self, agent_config):
        command = ["pbench-list-tools", "--group", "foo", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
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
        assert exitcode == 1

    def test_option(self, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert exitcode == 0


class Test_list_tool_tools_registered:
    @pytest.fixture
    def tool(self, pbench_run):
        p = pbench_run / "tools-v1-default" / "testhost.example.com"
        p.mkdir(parents=True)
        tool = p / "perf"
        tool.touch()
        return tool

    def test_help(self, tool, agent_config):
        command = ["pbench-list-tools", "--help"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"Usage: pbench-list-tools [OPTIONS]" in out
        assert exitcode == 0

    def test_no_args(self, tool, agent_config):
        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"default: testhost.example.com ['perf']\n" == out
        assert exitcode == 0

    def test_group_existing(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"default: testhost.example.com ['perf']\n" == out
        assert exitcode == 0

    def test_name_existing(self, tool, agent_config):
        command = ["pbench-list-tools", "-n", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"tool name: perf groups: default\n" == out
        assert exitcode == 0

    def test_non_existent_group(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_non_existent_name(self, tool, agent_config):
        command = ["pbench-list-tools", "-n", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        # XXX 0.69.9 backward compatibility: non-existent names do not return errors
        assert exitcode == 0

    def test_existing_group_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default", "--name", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"tool name: perf groups: default\n" == out
        assert exitcode == 0

    def test_existing_group_non_existent_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default", "--name", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 0

    def test_non_existent_group_existing_name(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "unknown", "--name", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1


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
        return

    def test_existing_group_options(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "default", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        # XXX this is the current output - pretty ugly
        assert (
            b"default: testhost.example.com [('iostat', '--interval=30'), ('mpstat', '--interval=300')]\n"
            == out
        )
        assert exitcode == 0

    def test_non_existent_group_options(self, tool, agent_config):
        command = ["pbench-list-tools", "--group", "unknown", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
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
        # XXX this is the current output - obviously wrong
        assert b"tool name: mpstat groups: default\n" == out
        assert exitcode == 0

    def test_option(self, tool, agent_config):
        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        # XXX this is the current output - pretty ugly
        assert (
            b"default: testhost.example.com [('iostat', '--interval=30'), ('mpstat', '--interval=300')]\ntest: testhost.example.com [('iostat', '--interval=30'), ('mpstat', '--interval=300')]\n"
            == out
        )
        assert exitcode == 0
