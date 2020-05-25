import configparser

import pytest


def get_agent_config(f):
    c = configparser.ConfigParser()
    c.read(f)
    return c


def test_pbench_config_activate_help():
    command = ["pbench-agent-config-activate", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_config_activate_help_failed():
    command = ["pbench-agent-config-activate", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_config_activate(
    tmpdir, create_agent_environment, pbench_installdir, pbench_conf
):
    conf = pbench_installdir / "config" / "pbench-agent.cfg"
    pbench_installdir = pbench_installdir / "config"
    pbench_installdir.mkdir()
    command = ["pbench-agent-config-activate", pbench_conf]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert conf.exists() is True

    c = pytest.helpers.get_pbench_config(conf)
    conf = pytest.helpers.get_pbench_config(pbench_conf)
    assert conf.get("pbench-agent", "install-dir") == c.get(
        "pbench-agent", "install-dir"
    )
