import os
import shutil
import pytest

from pbench.server.api import create_app


@pytest.fixture(scope="session", autouse=True)
def setup(request):
    """Test package setup"""
    print("Test SETUP")
    os.makedirs("./srv/pbench/tmp", exist_ok=True)
    os.makedirs("./srv/pbench/logs", exist_ok=True)
    os.makedirs(
        "./srv/pbench/pbench-move-results-receive/fs-version-002", exist_ok=True
    )
    os.makedirs("./opt/pbench-server/bin", exist_ok=True)
    os.makedirs("./opt/pbench-server/lib/config", exist_ok=True)
    shutil.copyfile(
        "./server/lib/config/pbench-server-default.cfg",
        "./opt/pbench-server/lib/config/pbench-server-default.cfg",
    )
    shutil.copyfile(
        "./lib/pbench/test/unit/config/pbench-server.cfg",
        "./opt/pbench-server/lib/config/pbench-server.cfg",
    )

    def teardown():
        """Test package teardown"""
        print("Test TEARDOWN")
        shutil.rmtree("./srv/")
        shutil.rmtree("./opt/")

    request.addfinalizer(teardown)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "_PBENCH_SERVER_CONFIG", "./opt/pbench-server/lib/config/pbench-server.cfg"
    )
    app = create_app()
    app.testing = True
    """A test client for the app."""
    app_client = app.test_client()
    app_client.config = app.config
    return app_client
