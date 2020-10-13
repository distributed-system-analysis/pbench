import pytest


def test_pbench_clear_results_help():
    command = ["pbench-clear-results", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-clear-results [OPTIONS]" in out
    assert exitcode == 0


def test_clear_results(monkeypatch, agent_config, pbench_run, pbench_cfg):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    tool_default = pbench_run / "tools-v1-default" / "testhost.example.com"
    tool_default.mkdir(parents=True)
    mpstat = tool_default / "mpstat"
    mpstat.touch()

    tmp_dir = pbench_run / "tmp" / "leave-me"
    tmp_dir.mkdir(parents=True)
    tmp_dir = tmp_dir / "alone"
    tmp_dir.touch()

    junk = pbench_run / "foo"
    junk.touch()

    # test-63
    command = ["pbench-clear-results"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0

    assert tool_default.exists() is True
    assert tmp_dir.exists() is True
    assert junk.exists() is False
