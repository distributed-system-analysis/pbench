import pytest


def test_pbench_list_tools_help():
    command = ["pbench-register-tool", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_register_tools_help_failed():
    command = ["pbench-register-tool", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_register_tools(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)

    command = ["pbench-register-tool", "--name", "disk", "--group", "foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    result = pbench_run / "tools-foo" / "disk"
    assert result.exists() is True
    assert b"disk tool is now registered in group foo\n" in out
