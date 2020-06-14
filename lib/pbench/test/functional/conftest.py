import subprocess

import pytest
from pbench.test.unit.agent.conftest import base_setup


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    return base_setup(request, pytestconfig)

@pytest.helpers.register
def capture(command):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,)
    out, err = proc.communicate()
    return out, err, proc.returncode
