import shutil
import tempfile
import pytest
from pathlib import Path

from pbench.server.api import create_app


server_cfg_tmpl = """[DEFAULT]
install-dir = {TMP}/opt/pbench-server

[pbench-server]
pbench-top-dir = {TMP}/srv/pbench

###########################################################################
# The rest will come from the default config file.
[config]
path = %(install-dir)s/lib/config
files = pbench-server-default.cfg
"""


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    """Test package setup for pbench-server"""
    print("Test SETUP for pbench-server")

    # Create a single temporary directory for the "/srv/pbench" and
    # "/opt/pbench-server" directories.
    TMP = tempfile.TemporaryDirectory(suffix=".d", prefix="pbench-server-unit-tests.")
    tmp_d = Path(TMP.name)

    srv_pbench = tmp_d / "srv" / "pbench"
    pbench_tmp = srv_pbench / "tmp"
    pbench_tmp.mkdir(parents=True, exist_ok=True)
    pbench_logs = srv_pbench / "logs"
    pbench_logs.mkdir(parents=True, exist_ok=True)
    pbench_recv = srv_pbench / "pbench-move-results-receive" / "fs-version-002"
    pbench_recv.mkdir(parents=True, exist_ok=True)

    opt_pbench = tmp_d / "opt" / "pbench-server"
    pbench_bin = opt_pbench / "bin"
    pbench_bin.mkdir(parents=True, exist_ok=True)
    pbench_cfg = opt_pbench / "lib" / "config"
    pbench_cfg.mkdir(parents=True, exist_ok=True)

    # "Install" the default server configuration file.
    shutil.copyfile(
        "./server/lib/config/pbench-server-default.cfg",
        str(pbench_cfg / "pbench-server-default.cfg"),
    )

    cfg_file = pbench_cfg / "pbench-server.cfg"
    with cfg_file.open(mode="w") as fp:
        fp.write(server_cfg_tmpl.format(TMP=TMP.name))

    pytestconfig.cache.set("TMP", TMP.name)
    pytestconfig.cache.set("_PBENCH_SERVER_CONFIG", str(cfg_file))

    def teardown():
        """Test package teardown for pbench-server"""
        print("Test TEARDOWN for pbench-server")
        TMP.cleanup()

    request.addfinalizer(teardown)


@pytest.fixture
def client(pytestconfig, monkeypatch):
    cfg_file = pytestconfig.cache.get("_PBENCH_SERVER_CONFIG", None)
    monkeypatch.setenv("_PBENCH_SERVER_CONFIG", cfg_file)
    app = create_app()
    app.testing = True
    """A test client for the app."""
    app_client = app.test_client()
    app_client.config = app.config
    return app_client
