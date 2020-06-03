import pytest


def test_pbench_list_triggers_help():
    command = ["pbench-list-triggers", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_list_triggers_help_failed():
    command = ["pbench-list-triggers", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_list_triggers(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)

    default = pbench_run / "tools-default"
    default.mkdir()
    foo = default / "disk"
    foo.write("")

    triggers = pbench_run / "tool-triggers"
    triggers.write(
        "\n" "default:START DEFAULT:STOP DEFAULT\n" "foo:START FOO:STOP FOO\n"
    )

    command = ["pbench-list-triggers"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert "b'default:START DEFAULT:STOP DEFAULT\n'"
    assert exitcode == 0

    command = ["pbench-list-triggers", "--group", "default"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert "b'default:START DEFAULT:STOP DEFAULT\n'"
    assert exitcode == 0

    command = ["pbench-list-triggers", "--group", "default"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"default:START DEFAULT:STOP DEFAULT\n" in out
    assert exitcode == 0
