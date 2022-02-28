import os
import pytest
import subprocess

from pbench.test.unit.agent.conftest import base_setup


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    return base_setup(request, pytestconfig)


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
