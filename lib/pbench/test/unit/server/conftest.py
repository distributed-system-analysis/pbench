from configparser import ConfigParser
import datetime
import hashlib
from http import HTTPStatus
import os
import uuid
from pathlib import Path
from posix import stat_result
import shutil
from stat import ST_MTIME
import tarfile
from typing import Dict

from email_validator import EmailNotValidError, ValidatedEmail
from freezegun import freeze_time
import pytest

from pbench.server import PbenchServerConfig
from pbench.server.api import create_app, get_server_config
from pbench.server.api.auth import Auth
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.template import Template
from pbench.server.database.models.users import User
from pbench.server.filetree import Tarball
from pbench.test import on_disk_config
from pbench.test.unit.server.headertypes import HeaderTypes

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


def do_setup(tmp_d: Path) -> Path:
    """Perform on disk server config setup."""
    # Create a single temporary directory for the "/srv/pbench" and
    # "/opt/pbench-server" directories.
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
    cfg_file.write_text(server_cfg_tmpl.format(TMP=str(tmp_d)))

    return pbench_cfg


@pytest.fixture(scope="session")
def on_disk_server_config(tmp_path_factory) -> Dict[str, Path]:
    """Test package setup for pbench-server"""
    return on_disk_config(tmp_path_factory, "server", do_setup)


@pytest.fixture()
def server_config(on_disk_server_config, monkeypatch) -> PbenchServerConfig:
    """
    Mock a pbench-server.cfg configuration as defined above.

    Args:
        on_disk_server_config: the on-disk server configuration setup
        monkeypatch: testing environment patch fixture

    Returns:
        a PbenchServerConfig object the test case can use
    """
    cfg_file = on_disk_server_config["cfg_dir"] / "pbench-server.cfg"
    monkeypatch.setenv("_PBENCH_SERVER_CONFIG", str(cfg_file))

    server_config = get_server_config()
    return server_config


@pytest.fixture()
def client(server_config, fake_email_validator):
    """A test client for the app.

    Fixtures:
        server_config: Set up a pbench-server.cfg configuration
        fake_email_validator: Many tests use the Flask client initialized here
            to register users, and we need that client to be bound to our
            fake validator mock. Establishing it here makes the binding
            universal.

    NOTE: The Flask app initialization includes setting up the SQLAlchemy DB.
    For test cases that require the DB but not a full Flask app context, use
    the db_session fixture instead, which adds DB cleanup after the test.
    """
    app = create_app(server_config)

    app_client = app.test_client()
    app_client.logger = app.logger
    app_client.config = app.config
    app_client.debug = True
    app_client.testing = True
    return app_client


@pytest.fixture()
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
def fake_email_validator(monkeypatch):
    """
    Set up a mock for the email validator so we control failure modes.
    """

    def fake_email(value: str, **kwargs) -> ValidatedEmail:

        # The email validation failure case needs to see an error
        if "," in value:
            raise EmailNotValidError("testing")

        # Return just the part of ValidatedEmail we use
        return ValidatedEmail(email=value)

    # The SQLAlchemy model decorator binds the function oddly, so we have to
    # reach into the module's namespace.
    monkeypatch.setattr(
        "pbench.server.database.models.users.validate_email", fake_email
    )


@pytest.fixture()
def create_user(client, fake_email_validator) -> User:
    """
    Construct a test user and add it to the database.

    Args:
        client: Fixture to ensure we have a database
    """
    user = User(
        email="test@example.com",
        password=generic_password,
        username="test",
        first_name="Test",
        last_name="Account",
    )
    user.add()
    return user


@pytest.fixture()
def create_admin_user(client, fake_email_validator) -> User:
    """
    Construct an admin user and add it to the database.

    Args:
        client: Fixture to ensure we have a database
    """
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
def attach_dataset(create_drb_user, create_user):
    """
    Create test Datasets for the authorized user ("drb") and for another user
    ("test")

    Args:
        create_drb_user: create a "drb" user
        create_user: create a "test" user
    """

    # The default time for the `uploaded` timestamp will be locked by the
    # "freeze_time" context manager, and overridden by an explicit value to
    # the constructor. We're testing both cases here by overriding "uploaded"
    # for one Dataset and letting it default for the other.
    with freeze_time("1970-01-01 00:42:00"):
        Dataset(
            owner="drb",
            created=datetime.datetime(2020, 2, 15),
            uploaded=datetime.datetime(2022, 1, 1),
            controller="node",
            name="drb",
            access="private",
            md5="random_md5_string1",
        ).add()
        Dataset(
            owner="test",
            created=datetime.datetime(2002, 5, 16),
            controller="node",
            name="test",
            access="private",
            md5="random_md5_string2",
        ).add()


@pytest.fixture()
def provide_metadata(attach_dataset):
    """
    Create "real" metadata in the backing database, which will be accessible
    via the un-mocked Metadata.getvalue() API.

    TODO: We really want to move away from using a backing DB for unit tests;
    see `get_document_map()` below for an alternative example. (But in many
    contexts, using "half DB" and "half mock" will result in SQLAlchemy
    confusion.)
    """
    drb = Dataset.query(name="drb")
    test = Dataset.query(name="test")
    Metadata.setvalue(dataset=drb, key="user.contact", value="me@example.com")
    Metadata.setvalue(dataset=drb, key=Metadata.DELETION, value="2022-12-25")
    Metadata.setvalue(
        dataset=drb,
        key="server.index-map",
        value={
            "unit-test.v6.run-data.2020-08": ["random_md5_string1"],
            "unit-test.v5.result-data-sample.2020-08": ["random_document_uuid"],
            "unit-test.v6.run-toc.2020-05": ["random_md5_string1"],
        },
    )
    Metadata.setvalue(dataset=test, key="user.contact", value="you@example.com")
    Metadata.setvalue(dataset=test, key=Metadata.DELETION, value="2023-01-25")


@pytest.fixture()
def get_document_map(monkeypatch, attach_dataset):
    """
    Mock a Metadata get call to return an Elasticsearch document index
    without requiring a DB query.

    Args:
        monkeypatch: patching fixture
        attach_dataset:  create a mock Dataset object
    """
    map = {
        "unit-test.v6.run-data.2021-06": [uuid.uuid4().hex],
        "unit-test.v6.run-toc.2021-06": [uuid.uuid4().hex for i in range(10)],
        "unit-test.v5.result-data-sample.2021-06": [
            uuid.uuid4().hex for i in range(20)
        ],
    }

    def get_document_map(dataset: Dataset, key: str) -> Metadata:
        assert key == Metadata.INDEX_MAP
        return map

    with monkeypatch.context() as m:
        m.setattr(Metadata, "getvalue", get_document_map)
        yield map


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
        elif name == "result-data-sample":
            return Template(
                name="result-data-sample",
                idxname="result-data-sample",
                template_name="unit-test.v5.result-data-sample",
                file="run.json",
                template_pattern="unit-test.v5.result-data-sample.*",
                index_template="unit-test.v5.result-data-sample.{year}-{month}",
                settings={"none": False},
                mappings={
                    "_meta": {"version": "5"},
                    "date_detection": "false",
                    "properties": {
                        "@timestamp": {"type": "date", "format": "dateOptionalTime"},
                        "@timestamp_original": {"type": "keyword", "index": "false"},
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
                                "measurement_title": {
                                    "type": "text",
                                    "fields": {"raw": {"type": "keyword"}},
                                },
                                "uid": {"type": "keyword"},
                            }
                        },
                        "benchmark": {
                            "properties": {
                                "name": {"type": "keyword"},
                                "bs": {"type": "keyword"},
                                "filename": {"type": "text"},
                                "frame_size": {"type": "long"},
                            }
                        },
                    },
                },
                version=5,
            )
        elif name == "result-data":
            return Template(
                name="result-data",
                idxname="result-data",
                template_name="unit-test.v5.result-data",
                file="result-data.json",
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


@pytest.fixture()
def pbench_admin_token(client, server_config, create_admin_user):
    # Login admin user to get valid pbench token
    response = login_user(client, server_config, admin_username, generic_password)
    assert response.status_code == HTTPStatus.OK
    data = response.json
    assert data["auth_token"]
    return data["auth_token"]


@pytest.fixture()
def create_drb_user(client, server_config, fake_email_validator):
    # Create a user
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


@pytest.fixture()
def pbench_token(client, server_config, create_drb_user):
    # Login user to get valid pbench token
    response = login_user(client, server_config, "drb", generic_password)
    assert response.status_code == HTTPStatus.OK
    data = response.json
    assert data["auth_token"]
    return data["auth_token"]


@pytest.fixture(params=[header for header in HeaderTypes])
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


@pytest.fixture()
def current_user_drb(monkeypatch, fake_email_validator):
    drb = User(
        email="drb@example.com",
        id=3,
        username="drb",
        first_name="Authorized",
        last_name="User",
    )

    class FakeHTTPTokenAuth:
        def current_user(self) -> User:
            return drb

    with monkeypatch.context() as m:
        m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
        yield drb


@pytest.fixture()
def current_user_none(monkeypatch):
    class FakeHTTPTokenAuth:
        def current_user(self) -> User:
            return None

    with monkeypatch.context() as m:
        m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
        yield None


@pytest.fixture()
def tarball(tmp_path):
    """
    Create a test tarball and MD5 file; the tarball is empty, but has a real
    MD5.

    This intentionally uses a weird and ugly file name that should be
    maintained through all the marshalling and unmarshalling on the wire until
    it lands on disk and in the Dataset.
    """
    filename = "pbench-user-benchmark_some + config_2021.05.01T12.42.42.tar.xz"
    datafile = tmp_path / filename
    metadata = ConfigParser()
    metadata.add_section("pbench")
    metadata.set("pbench", "date", "2002-05-16")
    metadata_file = tmp_path / "metadata.log"
    with metadata_file.open("w") as meta_fp:
        metadata.write(meta_fp)
    with tarfile.open(datafile, "w:xz") as tar:
        tar.add(str(metadata_file), arcname=f"{Tarball.stem(filename)}/metadata.log")
    md5 = hashlib.md5()
    md5.update(datafile.read_bytes())
    md5file = tmp_path / (filename + ".md5")
    md5file.write_text(md5.hexdigest())

    yield datafile, md5file, md5.hexdigest()

    # Clean up after the test case

    if md5file.exists():
        md5file.unlink()
    if datafile.exists():
        datafile.unlink()
