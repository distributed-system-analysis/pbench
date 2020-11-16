import os
import subprocess

import pytest

from pbench.test.agent.conftest import base_setup


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    return base_setup(request, pytestconfig)


@pytest.fixture
def pbench_run(tmpdir):
    pbench_run = tmpdir / "test/var/lib/pbench-agent"
    os.makedirs(pbench_run)
    yield pbench_run
