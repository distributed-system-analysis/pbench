import os
import pytest
import subprocess

from pbench.test.unit.agent.conftest import on_disk_agent_config


@pytest.fixture(scope="session", autouse=True)
def func_setup(tmp_path_factory):
    """Test package setup for functional tests"""
    return on_disk_agent_config(tmp_path_factory)


@pytest.helpers.register
def capture(command):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return out, err, proc.returncode


@pytest.fixture
def pbench_run(monkeypatch, tmp_path):
    assert "pbench_run" not in os.environ
    pbench_agent_d = tmp_path / "var" / "lib" / "pbench-agent"
    pbench_agent_d.mkdir(parents=True, exist_ok=True)

    yield pbench_agent_d
