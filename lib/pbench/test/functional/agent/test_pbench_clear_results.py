import pytest


def test_pbench_clear_tools_help():
    command = ["pbench-clear-results", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_clear_tools_help_failed():
    command = ["pbench-clear-results", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_clear_tools(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    fake_group = pbench_run / "tools-fake"
    fake_group.mkdir()
    fake_tmp = pbench_run / "tmp"
    fake_tmp.mkdir()
    fake_results = pbench_run / "pbench-fio"
    fake_results.mkdir()

    command = ["pbench-clear-results"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert fake_group.exists() is True
    assert fake_tmp.exists() is True
    assert fake_results.exists() is False
