import os

import pytest

from pbench.client import Pbench


@pytest.fixture(scope="module")
def pbench():
    """
    Used by Pbench Server functional tests to connect to a server.

    If run without a PBENCH_SERVER environment variable pointing to the server
    instance, this will fail the test run.
    """
    host = os.environ.get("PBENCH_SERVER")
    assert (
        host
    ), "Pbench Server functional tests require that PBENCH_SERVER be set to the hostname of a server"
    pbench = Pbench(host)
    assert pbench, f"Unable to connect to Pbench Server {host}"
    pbench.connect()
    return pbench
