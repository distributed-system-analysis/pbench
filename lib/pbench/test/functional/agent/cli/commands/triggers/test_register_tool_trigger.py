import pytest


def test_pbench_register_tool_trigger_help():
    command = ["pbench-register-tool-trigger", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-register-tool-trigger [OPTIONS]" in out
    assert exitcode == 0


def test_register_triggers(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """Verify triggers registered for default group"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    trigger_default = pbench_run / "tools-v1-default" / "testhost.example.com"
    trigger_default.mkdir(parents=True)
    pidstat = trigger_default / "pidstat"
    pidstat.touch()

    # test-15
    command = [
        "pbench-register-tool-trigger",
        "--group=default",
        "--start-trigger=START DEFAULT",
        "--stop-trigger=STOP DEFAULT",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    trigger = pbench_run / "tools-v1-default" / "__trigger__"
    assert trigger.exists()
    assert b"tool trigger strings for start:" in out
    assert "START DEFAULT:STOP DEFAULT\n" in trigger.read_text()


def test_register_triggers_invalid_start(
    monkeypatch, agent_config, pbench_run, pbench_cfg
):
    """pbench-register-tool-trigger with invalid start"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    trigger_default = pbench_run / "tools-v1-default" / "testhost.example.com"
    trigger_default.mkdir(parents=True)
    pidstat = trigger_default / "pidstat"
    pidstat.touch()

    command = [
        "pbench-register-tool-trigger",
        "--group=default",
        '--start-trigger="START:DEFAULT"',
        '--stop-trigger="STOP DEFAULT"',
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert (
        b"pbench-register-tool-trigger: the start trigger cannot have a colon in it:"
        in err
    )
    assert exitcode == 1


def test_register_triggers_invalid_stop(
    monkeypatch, agent_config, pbench_run, pbench_cfg
):
    """pbench-register-tool-trigger with invalid stop"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    trigger_default = pbench_run / "tools-v1-default" / "testhost.example.com"
    trigger_default.mkdir(parents=True)
    pidstat = trigger_default / "pidstat"
    pidstat.touch()
    command = [
        "pbench-register-tool-trigger",
        "--group=default",
        '--start-trigger="START DEFAULT"',
        '--stop-trigger="STOP:DEFAULT"',
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert (
        b"pbench-register-tool-trigger: the stop trigger cannot have a colon in it:"
        in err
    )
    assert exitcode == 1
