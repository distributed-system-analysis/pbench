import pytest


def test_pbench_clear_tools_help():
    command = ["pbench-clear-tools", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_clear_tools_help_failed():
    command = ["pbench-clear-tools", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_clear_tools(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    fake_group = pbench_run / "tools-fake"
    fake_group.mkdir()
    fake_tmp = pbench_run / "tools-fake" / "foo"
    fake_tmp.write("")
    fake_perf = fake_group / "perf"
    fake_perf.write("")

    default = pbench_run / "tools-default"
    default.mkdir()
    foo_default = default / "foo"
    foo_default.write("")

    command = ["pbench-clear-tools"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert foo_default.exists() is False

    command = ["pbench-clear-tools", "-n", "foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert foo_default.exists() is False

    command = ["pbench-clear-tools", "-n", "perf", "-g", "fake"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert fake_perf.exists() is False
