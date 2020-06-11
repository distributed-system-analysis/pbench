import pytest
from pbench.test.unit.agent.conftest import base_setup


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    return base_setup(request, pytestconfig)
