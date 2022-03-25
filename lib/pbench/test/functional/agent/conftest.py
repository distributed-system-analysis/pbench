import os
from pathlib import Path
import pytest
import subprocess
from typing import Dict

from pbench.test import on_disk_config
from pbench.test.unit.agent.conftest import do_setup


@pytest.fixture(scope="session", autouse=True)
def func_setup(tmp_path_factory) -> Dict[str, Path]:
    """Test package setup for functional tests"""
    return on_disk_config(tmp_path_factory, "agent", do_setup)


@pytest.helpers.register
def capture(command):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return out, err, proc.returncode


@pytest.fixture
def pbench_run(tmp_path):
    assert "pbench_run" not in os.environ
    pbench_agent_d = tmp_path / "var" / "lib" / "pbench-agent"
    pbench_agent_d.mkdir(parents=True, exist_ok=True)

    yield pbench_agent_d
