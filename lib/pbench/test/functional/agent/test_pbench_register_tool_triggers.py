import pytest


def test_pbench_register_tool_triggers_help():
    command = ["pbench-register-tool-triggers", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_register_tool_triggers_help_failed():
    command = ["pbench-register-tool-triggers", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_register_tool_triggers(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    pbench_run = pbench_run / "tools-default"
    pbench_run.mkdir()
    command = [
        "pbench-register-tool-triggers",
        "--group",
        "default",
        "--start-trigger",
        "START DEFAULT",
        "--stop-trigger",
        "STOP DEFAULT",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    msg = b"tool trigger strings for start: START DEFAULT and stop: STOP DEFAULT are now registerd\n"
    assert msg in out
    assert exitcode == 0

    command = [
        "pbench-register-tool-triggers",
        "--group",
        "default",
        "--start-trigger",
        "START:DEFAULT",
        "--stop-trigger",
        "STOP DEFAULT",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1

    command = [
        "pbench-register-tool-triggers",
        "--group",
        "default",
        "--start-trigger",
        "START DEFAULT",
        "--stop-trigger",
        "STOP:DEFAULT",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1
