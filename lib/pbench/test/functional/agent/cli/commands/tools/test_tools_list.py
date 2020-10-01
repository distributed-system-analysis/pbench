import pytest


def test_pbench_list_tools_help():
    command = ["pbench-list-tools", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-list-tools [OPTIONS]" in out
    assert exitcode == 0


def test_list_tool(monkeypatch, agent_config, pbench_run, pbench_cfg):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    p = pbench_run / "tools-v1-default" / "testhost.example.com"
    p.mkdir(parents=True)
    tool = p / "perf"
    tool.touch()

    command = ["pbench-list-tools"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"default: testhost.example.com ['perf']" in out

    command = ["pbench-list-tools", "--group", "default"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"default: testhost.example.com ['perf']" in out

    command = ["pbench-list-tools", "-n", "perf"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"tool name: perf groups: default" in out
