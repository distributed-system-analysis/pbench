import pytest


def test_pbench_config_ssh_key_help():
    command = ["pbench-agent-config-ssh-key", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_config_ssh_key_help_failed():
    command = ["pbench-agent-config-ssh-key", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_config_ssh_key(
    tmpdir, create_agent_environment, pbench_installdir, pbench_conf
):
    fake_key = tmpdir / "id_rsa"
    fake_key.write("")

    command = ["pbench-agent-config-ssh-key", pbench_conf, fake_key]
    out, err, exitcode = pytest.helpers.capture(command)
    print(err.decode("utf-8"))
    print(out.decode("utf-8"))
    assert exitcode == 0
    fake_key = pbench_installdir / "id_rsa"
    assert fake_key.exists() is True
