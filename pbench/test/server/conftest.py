import os
import shutil
import pytest

from pbench.lib.server.api.config import ServerConfig
from pbench.cli.server.shell import create_app
from pbench.test.server.common import mock_get_config_prefix


@pytest.fixture(scope="session", autouse=True)
def setup(request):
    """Test package setup"""
    print("Test SETUP")
    os.makedirs("./srv/pbench/tmp", exist_ok=True)
    os.makedirs("./srv/pbench/logs", exist_ok=True)
    os.makedirs("./opt/pbench-server/bin", exist_ok=True)
    os.makedirs("./opt/pbench-server/lib", exist_ok=True)

    def teardown():
        """Test package teardown"""
        print("Test TEARDOWN")
        shutil.rmtree("./srv/")
        shutil.rmtree("./opt/")

    request.addfinalizer(teardown)


@pytest.fixture
def client(monkeypatch):
    app = create_app()
    monkeypatch.setattr(ServerConfig, "get_server_config", mock_get_config_prefix(app))
    app.testing = True
    """A test client for the app."""
    app_client = app.test_client()
    app_client.config = app.config
    return app_client
