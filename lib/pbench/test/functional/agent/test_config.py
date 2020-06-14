import configparser
import shutil

import pytest


def get_agent_config(f):
    c = configparser.ConfigParser()
    c.read(f)
    return c


@pytest.fixture
def pbench_config_activate_init(tmpdir, create_agent_environment, pbench_installdir):
    pbench_install_dir = pbench_installdir / "config"
    pbench_install_dir.mkdir()


def test_pbench_config_help():
    command = ["pbench", "config", "activate", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_activate(pbench_config_activate_init, pbench_installdir, pbench_conf):
    conf = pbench_installdir / "config" / "pbench-agent.cfg"
    command = ["pbench", "config", "activate", pbench_conf]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert conf.exists() is True

    c = pytest.helpers.get_pbench_config(conf)
    conf = pytest.helpers.get_pbench_config(pbench_conf)
    assert conf.get("pbench-agent", "install-dir") == c.get(
        "pbench-agent", "install-dir"
    )


def test_failed_copy(pbench_config_activate_init, pbench_installdir, pbench_conf):
    command = ["pbench", "config", "activate", pbench_conf]
    shutil.rmtree(pbench_installdir)
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1
    assert b"does not exist" in out


def test_misssing_config():
    command = ["pbench", "config", "activate", "foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"'CONFIG': Path 'foo' does not exist.\n" in err
    assert exitcode == 2
