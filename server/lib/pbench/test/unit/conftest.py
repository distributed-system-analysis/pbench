"""This module builts base setup for Server side testing.
It is implicitly included by PyTest for all unit tests and provides
test fixtures and other definitions common across the Server unit tests"""
import logging
import tempfile
from pathlib import Path

import pytest
from pbench import _PbenchLogFormatter, _StyleAdapter


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    """Test package setup for pbench-server"""

    # Create a single temporary directory for the "/srv/pbench" and
    # "/opt/pbench-server" directories.
    tmp = tempfile.TemporaryDirectory(suffix=".d", prefix="pbench-server-unit-tests.")
    tmp_d = Path(tmp.name)

    pytestconfig.cache.set("TMP", str(tmp_d))
    request.addfinalizer(lambda: tmp.cleanup())


@pytest.fixture
def logger(pytestconfig):
    tmp = Path(pytestconfig.cache.get("TMP", None))
    logger = logging.getLogger("testing")
    handler = logging.FileHandler(tmp / "test.log")
    handler.setLevel(logging.ERROR)
    logfmt = (
        "1970-01-01T00:00:42.000000 {levelname} {name}.{module} {funcName} -- {message}"
    )
    formatter = _PbenchLogFormatter(fmt=logfmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return _StyleAdapter(logger)
