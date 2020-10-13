import pytest


def test_pbench_list_triggers_help():
    command = ["pbench-list-triggers", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-list-triggers [OPTIONS]" in out
    assert exitcode == 0


def test_list_triggers(monkeypatch, agent_config, pbench_run, pbench_cfg):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    trigger_default = pbench_run / "tools-v1-default"
    trigger_default.mkdir(parents=True)
    trigger_default = trigger_default / "__trigger__"
    with open(trigger_default, "w") as f:
        f.write("START DEFAULT:STOP DEFAULT")

    trigger_foo = pbench_run / "tools-v1-foo"
    trigger_foo.mkdir(parents=True)
    trigger_foo = trigger_foo / "__trigger__"
    with open(trigger_foo, "w") as f:
        f.write("START FOO:STOP FOO")

    # test-16
    command = ["pbench-list-triggers"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"default: START DEFAULT:STOP DEFAULT\nfoo: START FOO:STOP FOO\n" in out
    assert exitcode == 0

    # test-17
    command = ["pbench-list-triggers", "--group", "default"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"START DEFAULT:STOP DEFAULT" in out
    assert exitcode == 0

    # test-18
    command = ["pbench-list-triggers", "--group", "foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"START FOO:STOP FOO\n" in out
    assert exitcode == 0
