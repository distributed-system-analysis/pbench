import pytest


def test_pbench_list_tools_help():
    command = ["pbench-list-tools", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_clear_tools_help_failed():
    command = ["pbench-list-tools", "--foo"]
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

    command = ["pbench-list-tools"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"fake: foo, perf\ndefault: foo\n" in out

    command = ["pbench-list-tools", "-n", "foo", "-g", "foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"You cannot specify both group and name\n" in out
    assert exitcode == 1

    command = ["pbench-list-tools", "-g", "fake"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"fake: foo, perf\n" in out
