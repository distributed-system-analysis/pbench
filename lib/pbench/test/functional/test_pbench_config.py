import pytest


def test_pbench_config():
    command = ["pbench-config"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1


def test_pbench_config_help():
    command = ["pbench-config", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"--help" in out
    assert exitcode == 0


def test_pbench_agent_config(monkeypatch, tmpdir):
    cfg = tmpdir / "pbench-agent.cfg"
    pbench_config = """
    [pbench-agent]
    pbench_run = /tmp
    """
    cfg.write(pbench_config)
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(cfg))
    command = ["pbench-config", "pbench_run", "pbench-agent"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"/tmp" in out
    assert exitcode == 0
