import pytest


def test_pbench_agent_config_activate_help():
    command = ["pbench-agent-config-activate", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-agent-config-activate [OPTIONS]" in out
    assert exitcode == 0


def test_pbench_agent_config_ssh_key_help():
    command = ["pbench-agent-config-ssh-key", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-agent-config-ssh-key [OPTIONS]" in out
    assert exitcode == 0


def test_pbench_config_activate(tmp_path, opt_pbench, pbench_run):
    """test-14"""
    pbench_conf = """
    [pbench-agent]
    install-dir = %s
    pbench_run = %s
    [results]
    """ % (
        str(opt_pbench),
        str(pbench_run),
    )

    config = tmp_path / "pbench-agent.cfg"
    config.write_text(pbench_conf)
    cfg = opt_pbench / "config" / "pbench-agent.cfg"

    conf = opt_pbench / "config"
    conf.mkdir(parents=True)
    command = ["pbench-agent-config-activate", str(config)]
    err, out, exitcode = pytest.helpers.capture(command)
    assert cfg.exists() is True
    assert exitcode == 0


def test_pench_config_ssh_key(
    monkeypatch, tmp_path, agent_config, opt_pbench, pbench_run, pbench_cfg
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    fake_key = tmp_path / "id_rsa.pub"
    fake_key.touch()
    key = opt_pbench / "id_rsa"

    command = ["pbench-agent-config-ssh-key", str(pbench_cfg), str(fake_key)]
    err, out, exitcode = pytest.helpers.capture(command)
    assert key.exists() is True
    assert exitcode == 1
