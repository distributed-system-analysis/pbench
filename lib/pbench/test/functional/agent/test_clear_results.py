import pytest


def test_pbench_results_clear_help():
    command = ["pbench", "results", "clear", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0


def test_pbench_results_clear_help_fail():
    command = ["pbench", "results", "clear", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_clear_tools_with_env(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    fake_group = pbench_run / "tools-fake"
    fake_group.mkdir()
    fake_tmp = pbench_run / "tmp"
    fake_tmp.mkdir()
    fake_results = pbench_run / "pbench-fio"
    fake_results.mkdir()

    command = ["pbench", "results", "clear"]
    out, err, exitcode = pytest.helpers.capture(command)
    print(err.decode("utf-8"))
    assert exitcode == 0
    assert fake_group.exists() is False
    assert fake_tmp.exists() is False
    assert fake_results.exists() is True


def test_pbench_clear_tools_with_config(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    fake_group = pbench_run / "tools-fake"
    fake_group.mkdir()
    fake_tmp = pbench_run / "tmp"
    fake_tmp.mkdir()
    fake_results = pbench_run / "pbench-fio"
    fake_results.mkdir()

    command = ["pbench", "results", "clear", "-C", pbench_conf]
    out, err, exitcode = pytest.helpers.capture(command)
    print(err.decode("utf-8"))
    assert exitcode == 0
    assert fake_group.exists() is False
    assert fake_tmp.exists() is False
    assert fake_results.exists() is True
