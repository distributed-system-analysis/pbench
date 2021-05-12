import datetime
import os
import pytest
import shutil
import tempfile
from pathlib import Path
from posix import stat_result
from stat import ST_MTIME

from pbench.server.api import create_app, get_server_config
from pbench.server.api.auth import Auth
from pbench.server.database.database import Database
from pbench.server.database.models.template import Template

server_cfg_tmpl = """[DEFAULT]
install-dir = {TMP}/opt/pbench-server
default-host = pbench.example.com

[pbench-server]
pbench-top-dir = {TMP}/srv/pbench

[Postgres]
db_uri = sqlite:///:memory:

[elasticsearch]
host = elasticsearch.example.com
port = 7080

[graphql]
host = graphql.example.com
port = 7081

[logging]
logger_type = file

[Indexing]
index_prefix = unit-test


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
def server_config(pytestconfig, monkeypatch):
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

    server_config = get_server_config()
    return server_config


@pytest.fixture
def client(server_config):
    """A test client for the app.

    NOTE: the db_session fixture does something similar, but with implicit
    cleanup after the test, and without the Flask app setup DB tests don't
    require.
    """
    app = create_app(server_config)

    app_client = app.test_client()
    app_client.logger = app.logger
    app_client.config = app.config
    app_client.debug = True
    app_client.testing = True
    return app_client


@pytest.fixture
def db_session(server_config):
    """
    Construct a temporary DB session for the test case that will reset on
    completion.

    NOTE: the client fixture does something similar, but without the implicit
    cleanup, and with the addition of a Flask context that non-API tests don't
    require.

    Args:
        server_config: pbench-server.cfg fixture
    """
    Database.init_db(server_config, None)
    yield
    Database.db_session.remove()


@pytest.fixture
def user_ok(monkeypatch):
    """
    Override the Auth.validate_user method to pass without checking the
    database.
    """

    def ok(user: str) -> str:
        return user

    monkeypatch.setattr(Auth, "validate_user", ok)


@pytest.fixture()
def fake_mtime(monkeypatch):
    """
    Template's init event listener provides the file's modification date to
    support template version control. For unit testing, mock the stat results
    to appear at a fixed time.

    Args:
        monkeypatch: patch fixture
    """

    def fake_stat(file: str):
        """
        Create a real stat_result using an actual file, but change the st_mtime
        to a known value before returning it.

        Args:
            file: filename (not used)

        Returns:
            mocked stat_results
        """
        s = os.stat(".")
        t = int(datetime.datetime(2021, 1, 29, 0, 0, 0).timestamp())
        f = list(s)
        f[ST_MTIME] = t
        return stat_result(f)

    with monkeypatch.context() as m:
        m.setattr(Path, "stat", fake_stat)
        yield


@pytest.fixture()
def find_template(monkeypatch, fake_mtime):
    """
    Mock a Template class find call to return an object without requiring a DB
    query.

    Args:
        monkeypatch: patching fixture
        fake_mtime: fake file modification time on init
    """

    def fake_find(name: str) -> Template:
        return Template(
            name="run",
            idxname="run-data",
            template_name="unit-test.v6.run-data",
            file="run.json",
            template_pattern="unit-test.v6.run-data.*",
            index_template="unit-test.v6.run-data.{year}-{month}",
            settings={"none": False},
            mappings={"properties": None},
            version=5,
        )

    with monkeypatch.context() as m:
        m.setattr(Template, "find", fake_find)
        yield
