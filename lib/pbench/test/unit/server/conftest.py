import datetime
from http import HTTPStatus
import os
import pytest
import shutil
import tempfile
from enum import IntEnum
from pathlib import Path
from posix import stat_result
from stat import ST_MTIME

from pbench.server.api import create_app, get_server_config
from pbench.server.api.auth import Auth
from pbench.server.database.database import Database
from pbench.server.database.models.template import Template
from pbench.server.database.models.users import User

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
# We run with DEBUG level logging during the server unit tests to help
# verify we are not emitting too many logs.
logging_level = DEBUG

[Indexing]
index_prefix = unit-test


###########################################################################
# The rest will come from the default config file.
[config]
path = %(install-dir)s/lib/config
files = pbench-server-default.cfg
"""

admin_username = "test_admin"
admin_email = "test_admin@example.com"
generic_password = "12345"


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


def register_user(
    client, server_config, email, username, password, firstname, lastname
):
    """
    Helper function to register a user using register API
    """
    return client.post(
        f"{server_config.rest_uri}/register",
        json={
            "email": email,
            "password": password,
            "username": username,
            "first_name": firstname,
            "last_name": lastname,
        },
    )


def login_user(client, server_config, username, password):
    """
    Helper function to generate a user authentication token
    """
    return client.post(
        f"{server_config.rest_uri}/login",
        json={"username": username, "password": password},
    )


@pytest.fixture()
def create_user() -> User:
    user = User(
        email="test@example.com",
        password=generic_password,
        username="test",
        first_name="Test",
        last_name="Account",
    )
    user.add()
    return user


@pytest.fixture
def create_admin_user() -> User:
    user = User(
        email=admin_email,
        password=generic_password,
        username=admin_username,
        first_name="Admin",
        last_name="Account",
        role="ADMIN",
    )
    user.add()
    return user


@pytest.fixture
def user_ok(monkeypatch, create_user):
    """
    Override the Auth.validate_user method to pass without checking the
    database.
    """

    def ok(user: str) -> str:
        return str(create_user.id)

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
        if name == "run":
            return Template(
                name="run",
                idxname="run-data",
                template_name="unit-test.v6.run-data",
                file="run.json",
                template_pattern="unit-test.v6.run-data.*",
                index_template="unit-test.v6.run-data.{year}-{month}",
                settings={"none": False},
                mappings={
                    "_meta": {"version": "6"},
                    "date_detection": "false",
                    "properties": {
                        "@generated-by": {"type": "keyword"},
                        "@metadata": {
                            "properties": {
                                "controller_dir": {"type": "keyword"},
                                "file-date": {"type": "date"},
                                "file-name": {"type": "keyword"},
                                "file-size": {"type": "long"},
                                "md5": {"type": "keyword"},
                                "pbench-agent-version": {"type": "keyword"},
                                "raw_size": {"type": "long"},
                                "result-prefix": {"type": "text"},
                                "satellite": {"type": "keyword"},
                                "tar-ball-creation-timestamp": {"type": "date"},
                                "toc-prefix": {"type": "text"},
                            }
                        },
                        "@timestamp": {"type": "date"},
                        "authorization": {
                            "properties": {
                                "access": {
                                    "type": "text",
                                    "fields": {
                                        "keyword": {
                                            "type": "keyword",
                                            "ignore_above": 256,
                                        }
                                    },
                                },
                                "owner": {
                                    "type": "text",
                                    "fields": {
                                        "keyword": {
                                            "type": "keyword",
                                            "ignore_above": 256,
                                        }
                                    },
                                },
                            }
                        },
                        "host_tools_info": {
                            "type": "nested",
                            "properties": {
                                "hostname": {"type": "keyword"},
                                "hostname-f": {"type": "keyword"},
                                "hostname-s": {"type": "keyword"},
                                "label": {"type": "keyword"},
                                "tools": {
                                    "properties": {
                                        "disk": {"type": "text"},
                                        "haproxy-ocp": {"type": "text"},
                                        "iostat": {"type": "text"},
                                        "mpstat": {"type": "text"},
                                        "oc": {"type": "text"},
                                        "perf": {"type": "text"},
                                        "pidstat": {"type": "text"},
                                        "pprof": {"type": "text"},
                                        "proc-interrupts": {"type": "text"},
                                        "proc-vmstat": {"type": "text"},
                                        "prometheus-metrics": {"type": "text"},
                                        "sar": {"type": "text"},
                                        "turbostat": {"type": "text"},
                                        "vmstat": {"type": "text"},
                                    }
                                },
                            },
                        },
                        "run": {
                            "properties": {
                                "config": {"type": "keyword"},
                                "controller": {"type": "keyword"},
                                "date": {"type": "date"},
                                "end": {"type": "date"},
                                "id": {"type": "keyword"},
                                "iterations": {"type": "text"},
                                "name": {"type": "keyword"},
                                "script": {"type": "keyword"},
                                "start": {"type": "date"},
                                "toolsgroup": {"type": "keyword"},
                                "user": {"type": "keyword"},
                            }
                        },
                        "sosreports": {
                            "type": "nested",
                            "properties": {
                                "hostname-f": {"type": "keyword"},
                                "hostname-s": {"type": "keyword"},
                                "inet": {
                                    "type": "nested",
                                    "properties": {
                                        "ifname": {"type": "keyword"},
                                        "ipaddr": {"type": "ip"},
                                    },
                                },
                                "inet6": {
                                    "type": "nested",
                                    "properties": {
                                        "ifname": {"type": "keyword"},
                                        "ipaddr": {"type": "keyword"},
                                    },
                                },
                                "md5": {"type": "keyword"},
                                "name": {"type": "keyword"},
                                "sosreport-error": {"type": "text"},
                            },
                        },
                    },
                },
                version=5,
            )
        elif name == "result":
            return Template(
                name="result",
                idxname="result-data",
                template_name="unit-test.v5.result-data",
                file="run.json",
                template_pattern="unit-test.v5.result-data.*",
                index_template="unit-test.v5.result-data.{year}-{month}",
                settings={"none": False},
                mappings={
                    "_meta": {"version": "5"},
                    "date_detection": "false",
                    "properties": {
                        "@timestamp": {"type": "date", "format": "dateOptionalTime"},
                        "@timestamp_original": {"type": "keyword", "index": "false"},
                        "result_data_sample_parent": {"type": "keyword"},
                        "run": {
                            "properties": {
                                "id": {"type": "keyword"},
                                "name": {"type": "keyword"},
                            }
                        },
                        "iteration": {
                            "properties": {
                                "name": {"type": "keyword"},
                                "number": {"type": "long"},
                            }
                        },
                        "sample": {
                            "properties": {
                                "@idx": {"type": "long"},
                                "name": {"type": "keyword"},
                                "measurement_type": {"type": "keyword"},
                                "measurement_idx": {"type": "long"},
                                "measurement_title": {"type": "text"},
                                "uid": {"type": "keyword"},
                            }
                        },
                        "result": {
                            "properties": {
                                "@idx": {"type": "long"},
                                "read_or_write": {"type": "long"},
                                "value": {"type": "double"},
                            }
                        },
                    },
                },
                version=5,
            )
        else:
            return None

    with monkeypatch.context() as m:
        m.setattr(Template, "find", fake_find)
        yield


@pytest.fixture
def pbench_admin_token(client, server_config, create_admin_user):
    # Login admin user to get valid pbench token
    response = login_user(client, server_config, admin_username, generic_password)
    assert response.status_code == HTTPStatus.OK
    data = response.json
    assert data["auth_token"]
    return data["auth_token"]


@pytest.fixture
def pbench_token(client, server_config):
    # First create a user
    response = register_user(
        client,
        server_config,
        username="drb",
        firstname="firstname",
        lastname="lastName",
        email="user@domain.com",
        password=generic_password,
    )
    assert response.status_code == HTTPStatus.CREATED

    # Login user to get valid pbench token
    response = login_user(client, server_config, "drb", generic_password)
    assert response.status_code == HTTPStatus.OK
    data = response.json
    assert data["auth_token"]
    return data["auth_token"]


class HeaderTypes(IntEnum):
    VALID = 1
    VALID_ADMIN = 2
    INVALID = 3
    EMPTY = 4

    @staticmethod
    def valid_headers():
        return [HeaderTypes.VALID, HeaderTypes.VALID_ADMIN]


@pytest.fixture(params=(header for header in HeaderTypes))
def build_auth_header(request, server_config, pbench_token, pbench_admin_token, client):
    if request.param == HeaderTypes.VALID_ADMIN:
        header = {"Authorization": "Bearer " + pbench_admin_token}

    elif request.param == HeaderTypes.VALID:
        header = {"Authorization": "Bearer " + pbench_token}

    elif request.param == HeaderTypes.INVALID:
        # Create an invalid token by logging the user out
        response = client.post(
            f"{server_config.rest_uri}/logout",
            headers=dict(Authorization="Bearer " + pbench_token),
        )
        assert response.status_code == HTTPStatus.OK
        header = {"Authorization": "Bearer " + pbench_token}

    elif request.param == HeaderTypes.EMPTY:
        header = {}

    else:
        assert False, f"Unexpected request.param value:  {request.param}"
    return {"header": header, "header_param": request.param}
