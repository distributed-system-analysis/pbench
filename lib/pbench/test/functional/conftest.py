import configparser
import os
import shutil
import subprocess

import pytest

from pbench.test.unit.agent.conftest import base_setup


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    return base_setup(request, pytestconfig)


@pytest.helpers.register
def capture(command):
    """Capture the command output and return the stdout, stderr,
    and errorcode.
    """
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return out, err, proc.returncode


@pytest.fixture
def pbench_run(tmpdir):
    """Create an agent run directory for a unittest."""
    pbench_run = tmpdir / "var/lib/pbench-agent"
    os.makedirs(pbench_run)
    yield pbench_run


@pytest.fixture
def pbench_install_dir(tmpdir):
    """Create an agent install directory for a unittest"""
    pbench_install_dir = tmpdir / "opt/pbench-agent"
    os.makedirs(pbench_install_dir)
    yield pbench_install_dir


@pytest.fixture
def pbench_agent_config(tmpdir, pbench_run, pbench_install_dir, pytestconfig):
    """Create a default agent configuration for a specific unittest."""
    config = configparser.ConfigParser()
    config_dir = tmpdir / "opt/pbench-agent/config"
    os.makedirs(config_dir)

    # Fail fast if the configuration is missing
    pbench_config = str(config_dir / "pbench-agent-default.cfg")
    shutil.copyfile(
        "./agent/config/pbench-agent-default.cfg",
        pbench_config,
    )

    config.read(pbench_config)
    config["pbench-agent"]["install-dir"] = str(pbench_install_dir)
    config["pbench-agent"]["pbench_run"] = str(pbench_run)
    with open(pbench_config, "w") as f:
        config.write(f)

    yield pbench_config
