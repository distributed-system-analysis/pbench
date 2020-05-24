import pytest


def test_pbench_cleanup_help():
    command = ["pbench-cleanup", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_cleanup_help_failed():
    command = ["pbench-cleanup", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_cleanup(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    pbench_run = pbench_run / "tools-foo"
    pbench_run.mkdir()
    assert pbench_run.exists()
    command = ["pbench-cleanup"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Cleaning up" in out
    assert b"" in err
    assert exitcode == 0
    assert pbench_run.exists() is False


def test_pbench_cleanup_failed(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    pbench_run = pbench_run / "tools-foo"
    pbench_run.mkdir()
    assert pbench_run.exists()
    command = ["pbench-cleanup"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1
    assert pbench_run.exists() is True
