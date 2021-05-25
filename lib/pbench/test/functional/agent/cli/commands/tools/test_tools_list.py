import pytest


class Test_list_tool_no_tools_registered:
    def test_help(self):
        command = ["pbench-list-tools", "--help"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"Usage: pbench-list-tools [OPTIONS]" in out
        assert exitcode == 0

    def test_no_args(self, monkeypatch, agent_config, pbench_run, pbench_cfg):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"" == out
        assert exitcode == 0

    def test_name(self, monkeypatch, agent_config, pbench_run, pbench_cfg):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--name", "foo"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 2

    def test_group(self, monkeypatch, agent_config, pbench_run, pbench_cfg):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "foo"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_group_name(self, monkeypatch, agent_config, pbench_run, pbench_cfg):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "foo", "--name", "iostat"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_group_options(self, monkeypatch, agent_config, pbench_run, pbench_cfg):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "foo", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_group_name_options(
        self, monkeypatch, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

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

    def test_option(self, monkeypatch, agent_config, pbench_run, pbench_cfg):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

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

    def test_help(self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg):
        command = ["pbench-list-tools", "--help"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"Usage: pbench-list-tools [OPTIONS]" in out
        assert exitcode == 0

    def test_no_args(self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"default: testhost.example.com ['perf']\n" == out
        assert exitcode == 0

    def test_group_existing(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "default"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"default: testhost.example.com ['perf']\n" == out
        assert exitcode == 0

    def test_name_existing(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "-n", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"tool name: perf groups: default\n" == out
        assert exitcode == 0

    def test_non_existent_group(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_non_existent_name(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "-n", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 2

    def test_existing_group_name(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "default", "--name", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert b"tool name: perf groups: default\n" == out
        assert exitcode == 0

    def test_existing_group_non_existent_name(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "default", "--name", "unknown"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 2

    def test_non_existent_group_existing_name(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "unknown", "--name", "perf"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_existing_group_options(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "default", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        # FIX
        assert b"" == out
        assert exitcode == 0

    def test_non_existent_group_options(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--group", "unknown", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        assert exitcode == 1

    def test_existing_group_name_options(
        self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg
    ):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = [
            "pbench-list-tools",
            "--group",
            "default",
            "--name",
            "perf",
            "--with-option",
        ]
        out, err, exitcode = pytest.helpers.capture(command)
        # FIX
        assert b"" == out
        assert exitcode == 0

    def test_option(self, monkeypatch, tool, agent_config, pbench_run, pbench_cfg):
        monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

        command = ["pbench-list-tools", "--with-option"]
        out, err, exitcode = pytest.helpers.capture(command)
        # FIX
        assert b"" == out
        assert exitcode == 0
