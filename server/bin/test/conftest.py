import configparser
import pytest
import shutil
import tempfile
from pathlib import Path

from pbench.server.api import get_server_config

server_cfg_tmpl = """[DEFAULT]
install-dir = {TMP}/opt/pbench-server
default-host = pbench.example.com

[pbench-server]
pbench-top-dir = {TMP}/srv/pbench
put-token = Authorization-token

[results]
server_rest_url = https://pbench.example.com/v2/1

[logging]
logger_type = file

###########################################################################
# The rest will come from the default config file.
[config]
path = %(install-dir)s/lib/config
files = pbench-server-default.cfg
"""


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    """Test package setup for pbench-server"""

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
    pbench_archive = srv_pbench / "archive" / "fs-version-001"
    pbench_archive.mkdir(parents=True, exist_ok=True)

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
        TMP.cleanup()

    request.addfinalizer(teardown)


@pytest.fixture
def valid_config(pytestconfig, monkeypatch):
    """
    Mock a pbench-server.cfg configuration as defined above.

    Args:
        pytestconfig: pytest environmental configuration fixture
        monkeypatch: testing environment patch fixture

    Returns:
        a PbenchServerConfig object the test case can use
    """
    cfg_file = pytestconfig.cache.get("_PBENCH_SERVER_CONFIG", None)
    monkeypatch.setenv("_PBENCH_SERVER_CONFIG", cfg_file)

    valid_config = get_server_config()
    return valid_config


@pytest.fixture
def invalid_config(pytestconfig):
    cfg_file = pytestconfig.cache.get("_PBENCH_SERVER_CONFIG", None)

    server_config = configparser.ConfigParser()
    server_config.read(cfg_file)
    server_config.set("pbench-server", "pbench-receive-dir-prefix", "")

    return server_config


@pytest.fixture
def invalid_value_config(pytestconfig):
    cfg_file = pytestconfig.cache.get("_PBENCH_SERVER_CONFIG", None)
    TMP = pytestconfig.cache.get("TMP", None)

    path = f"{TMP}/srv/pbench/pbench-move-results-receive/fs-version-001"
    server_config = configparser.ConfigParser()
    server_config.read(cfg_file)
    server_config.set("pbench-server", "pbench-receive-dir-prefix", path)

    return server_config


@pytest.fixture
def copy_tb():
    shutil.copy(
        "./lib/pbench/test/unit/server/fixtures/upload/log.tar.xz",
        "./server/bin/test/fixtures/upload/tarball",
    )
    shutil.copy(
        "./lib/pbench/test/unit/server/fixtures/upload/log.tar.xz.md5",
        "./server/bin/test/fixtures/upload/tarball",
    )
