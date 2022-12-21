import datetime
import hashlib
from http import HTTPStatus
import logging
import os
from pathlib import Path
from posix import stat_result
import re
import shutil
from stat import ST_MTIME
import tarfile
from typing import Dict, Optional
import uuid

from email_validator import EmailNotValidError, ValidatedEmail
from freezegun import freeze_time
import jwt
import pytest
from requests import Response

from pbench.common import MetadataLog
from pbench.common.logger import _PbenchLogFormatter, _StyleAdapter
from pbench.server import PbenchServerConfig
from pbench.server.api import create_app, get_server_config
import pbench.server.auth.auth as Auth
from pbench.server.database.database import Database
from pbench.server.database.models.active_token import ActiveToken
from pbench.server.database.models.dataset import Dataset, Metadata, States
from pbench.server.database.models.template import Template
from pbench.server.database.models.user import User
from pbench.server.globals import destroy_server_ctx, init_server_ctx, server
from pbench.test import on_disk_config
from pbench.test.unit.server.headertypes import HeaderTypes

server_cfg_tmpl = """[DEFAULT]
install-dir = {TMP}/opt/pbench-server

[pbench-server]
pbench-top-dir = {TMP}/srv/pbench

[database]
uri = sqlite:///:memory:

[elasticsearch]
host = elasticsearch.example.com
port = 7080

[logging]
logger_type = file
# We run with DEBUG level logging during the server unit tests to help
# verify we are not emitting too many logs.
logging_level = DEBUG

[Indexing]
index_prefix = unit-test

[authentication]
server_url = keycloak.example.com:0000
realm = pbench
client = pbench-client
secret = my_precious

###########################################################################
# The rest will come from the default config file.
[config]
path = %(install-dir)s/lib/config
files = pbench-server-default.cfg
"""

admin_username = "test_admin"
admin_email = "test_admin@example.com"
generic_password = "12345"
jwt_secret = "my_precious"


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
def server_config_obj(on_disk_server_config, monkeypatch):
    """Mock a pbench-server.cfg configuration as defined above.

    Args:
        on_disk_server_config: the on-disk server configuration setup
        monkeypatch: testing environment patch fixture

    Returns:
        a PbenchServerConfig object
    """
    cfg_file = on_disk_server_config["cfg_dir"] / "pbench-server.cfg"
    monkeypatch.setenv("_PBENCH_SERVER_CONFIG", str(cfg_file))
    return get_server_config()


@pytest.fixture()
def server_globals():
    """Setup the server global context variable."""
    init_server_ctx()
    yield
    destroy_server_ctx()


@pytest.fixture()
def server_config(server_config_obj, server_globals) -> PbenchServerConfig:
    """Setup the server config context variable."""
    assert server.config is None
    _fixture_config = server_config_obj
    server.config = _fixture_config
    yield
    assert server.config is _fixture_config
    server.config = None


@pytest.fixture(scope="session")
def session_logger():
    """Construct a single Pbench Logger object for the entire session."""
    logger = logging.getLogger("unit-tests-server")
    logger.setLevel(logging.DEBUG)
    handler = logging.NullHandler()
    logfmt = "{levelname} {module} {funcName} -- {message}"
    formatter = _PbenchLogFormatter(fmt=logfmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return _StyleAdapter(logger)


@pytest.fixture()
def server_logger(server_config, session_logger):
    """Setup the server logger context variable."""
    assert server.logger is None
    _fixture_logger = session_logger
    server.logger = _fixture_logger
    yield
    assert server.logger is _fixture_logger
    server.logger = None


@pytest.fixture()
def db_session(server_config, server_logger):
    """Construct a temporary DB session for the test case that will reset on
    completion.

    NOTE: the client fixture uses `create_app()` which also eventually calls
    Database.init_db().  As such, do not use the `client` fixture with
    `db_session`.

    Args:
        server_config: pbench-server.cfg fixture
        server_logger: logger fixture
    """
    assert server.db_session is None
    Database.init_db()
    assert server.db_session is not None
    db = server.db_session
    yield
    assert server.db_session is db
    server.db_session.remove()
    server.db_session = None


@pytest.fixture()
def client(server_config_obj, fake_email_validator):
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

    NOTE as well: the `create_app()` method sets up the server.config and
    .logger context variables, so don't use this fixture with `server_config`
    or `server_logger`.
    """
    app = create_app(server_config_obj)

    # Verfiy that the created Pbench Server Flask app also setup the server
    # context variables.
    assert server.config is not None
    assert server.db_session is not None
    assert server.logger is not None
    # We remember the context variables to verify during cleanup below.
    cf = server.config
    db = server.db_session
    lg = server.logger

    app_client = app.test_client()
    app_client.logger = app.logger
    app_client.config = app.config
    app_client.debug = True
    app_client.testing = True

    with app.app_context():
        yield app_client

    assert server.config is cf
    assert server.db_session is db
    assert server.logger is lg
    destroy_server_ctx()


@pytest.fixture()
def capinternal(caplog):
    def compare(message: str, response: Optional[Response]):
        uuid = r"[a-zA-Z\d]{8}-([a-zA-Z\d]{4}-){3}[a-zA-Z\d]{12}"
        name = r"\w+\s+"
        external = re.compile(f"Internal Pbench Server Error: log reference {uuid}")
        internal = re.compile(f"{name}Internal error {uuid}: {message}")
        if response:
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            assert external.match(response.json["message"])
        for r in caplog.get_records("call"):
            if r.levelno == logging.ERROR:
                if internal.match(str(r.msg)):
                    return
        assert (
            False
        ), f"Expected pattern {internal.pattern!r} not logged at level 'ERROR': {[str(r.msg) for r in caplog.get_records('call')]}"

    return compare


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
    monkeypatch.setattr("pbench.server.database.models.user.validate_email", fake_email)


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

    The resulting datasets are:

        Owner   Access  Date        Name
        ------- ------- ----------- ---------
        drb     private 2020-02-15  drb
        test    private 2002-05-16  test

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
            owner_id=str(create_drb_user.id),
            created=datetime.datetime(2020, 2, 15),
            uploaded=datetime.datetime(2022, 1, 1),
            state=States.INDEXED,
            name="drb",
            access="private",
            resource_id="random_md5_string1",
        ).add()
        Dataset(
            owner_id=str(create_user.id),
            created=datetime.datetime(2002, 5, 16),
            state=States.INDEXED,
            name="test",
            access="private",
            resource_id="random_md5_string2",
        ).add()


@pytest.fixture()
def more_datasets(
    client,
    attach_dataset,
    create_drb_user,
    create_admin_user,
    create_user,
):
    """
    Supplement the conftest.py "attach_dataset" fixture with a few more
    datasets so we can practice various queries. In combination with
    attach_dataset, the resulting datasets are:

        Owner   Access  Date        Name
        ------- ------- ----------- ---------
        drb     private 2020-02-15  drb
        test    private 2002-05-16  test
        drb     public  2020-02-15  fio_1
        test    public  2002-05-16  fio_2
        test    private 2022-12-08  uperf_1
        test    private 2022-12-09  uperf_2
        test    private 2022-12-10  uperf_3
        test    private 2022-12-11  uperf_4

    Args:
        client: Provide a Flask API client
        create_drb_user: Create the "drb" user
        create_admin_user: Create the "test_admin" user
        attach_dataset: Provide some datasets
    """
    with freeze_time("1978-06-26 08:00:00"):
        Dataset(
            owner_id=str(create_drb_user.id),
            created=datetime.datetime(2020, 2, 15),
            uploaded=datetime.datetime(2022, 1, 1),
            state=States.INDEXED,
            name="fio_1",
            access="public",
            resource_id="random_md5_string3",
        ).add()
        Dataset(
            owner_id=str(create_user.id),
            created=datetime.datetime(2002, 5, 16),
            state=States.INDEXED,
            name="fio_2",
            access="public",
            resource_id="random_md5_string4",
        ).add()
        Dataset(
            owner_id=str(create_user.id),
            created=datetime.datetime(2022, 12, 8),
            state=States.INDEXED,
            name="uperf_1",
            access="private",
            resource_id="random_md5_string5",
        ).add()
        Dataset(
            owner_id=str(create_user.id),
            created=datetime.datetime(2022, 12, 9),
            state=States.INDEXED,
            name="uperf_2",
            access="private",
            resource_id="random_md5_string6",
        ).add()
        Dataset(
            owner_id=str(create_user.id),
            created=datetime.datetime(2022, 12, 10),
            state=States.INDEXED,
            name="uperf_3",
            access="private",
            resource_id="random_md5_string7",
        ).add()
        Dataset(
            owner_id=str(create_user.id),
            created=datetime.datetime(2020, 12, 11),
            state=States.INDEXED,
            name="uperf_4",
            access="private",
            resource_id="random_md5_string8",
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
    Metadata.setvalue(dataset=drb, key="global.contact", value="me@example.com")
    Metadata.setvalue(
        dataset=drb, key=Metadata.DELETION, value="2022-12-25 00:00-04:00"
    )
    Metadata.setvalue(
        dataset=drb,
        key="server.index-map",
        value={
            "unit-test.v6.run-data.2020-08": ["random_md5_string1"],
            "unit-test.v5.result-data-sample.2020-08": ["random_document_uuid"],
            "unit-test.v6.run-toc.2020-05": ["random_md5_string1"],
        },
    )
    Metadata.create(
        dataset=drb,
        key=Metadata.METALOG,
        value={
            "pbench": {
                "date": "2020-02-15T00:00:00",
                "config": "test1",
                "script": "unit-test",
                "name": "drb",
            },
            "run": {"controller": "node1.example.com"},
        },
    )

    test = Dataset.query(name="test")
    Metadata.setvalue(dataset=test, key="global.contact", value="you@example.com")
    Metadata.setvalue(
        dataset=test, key=Metadata.DELETION, value="1979-11-01T00:00+00:00"
    )
    Metadata.create(
        dataset=test,
        key=Metadata.METALOG,
        value={
            "pbench": {
                "date": "2002-05-16T00:00:00",
                "config": "test2",
                "script": "unit-test",
                "name": "test",
            },
            "run": {"controller": "node2.example.com"},
        },
    )


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
def create_drb_user(client, fake_email_validator):
    # Create a user
    drb = User(
        email="drb@example.com",
        id=3,
        password=generic_password,
        username="drb",
        first_name="Authorized",
        last_name="User",
    )
    drb.add()
    return drb


@pytest.fixture()
def pbench_admin_token(client, create_admin_user):
    return generate_token(
        user=create_admin_user,
        username=admin_username,
        pbench_client_roles=["ADMIN"],
    )


@pytest.fixture()
def pbench_token(client, create_drb_user):
    """
    OIDC valid token for the 'drb' user.
    """
    return generate_token(username="drb", user=create_drb_user)


@pytest.fixture()
def pbench_token_invalid(client, create_drb_user):
    """
    OIDC invalid token for the 'drb' user
    """
    return generate_token(username="drb", user=create_drb_user, valid=False)


@pytest.fixture()
def get_token(pbench_admin_token):
    """This fixture yields a function value which can be called to get
    an OIDC token for the user corresponding to the specified username.
    """
    return lambda user: (
        pbench_admin_token if user == admin_username else generate_token(username=user)
    )


def generate_token(
    username: str,
    user: Optional[User] = None,
    pbench_client_roles: Optional[list[str]] = None,
    valid: bool = True,
) -> str:
    """
    Generates an OIDC JWT token that mimics a real OIDC token obtained
    from an OIDC compliant client login.

    Args:
        username: username to include in the token payload
        user: user attributes will be extracted from the user object to include
            in the token payload.
            If not provided, user object will be queried from the User table
            using username as the key.
            It is a responsibility of the caller to make sure the user exists
            in the 'User' table until we remove the User table completely.
        pbench_client_roles: List of any roles to add in the token payload
        valid: If True, the generated token will be valid for 10 mins.
               If False, generated token would be invalid and expired

    TODO: When we remove the User table we need to update this functionality's
        dependance on user table.

    Returns
        JWT token string
    """
    # Current time to encode in the token payload
    current_utc = datetime.datetime.now(datetime.timezone.utc)

    if not user:
        user = User.query(username=username)
        assert user
    offset = datetime.timedelta(minutes=10)
    exp = current_utc + (offset if valid else -offset)
    payload = {
        "exp": exp,
        "iat": current_utc,
        "jti": "541777b5-7127-408d-9dfb-71790f36c4c2",
        "iss": "https://auth-server.com/realms/pbench",
        "aud": ["broker", "account", "pbench-client"],
        "sub": user.id,
        "typ": "Bearer",
        "azp": "pbench-client",
        "session_state": "1988612e-774d-43b8-8d4a-bbc05ee55edb",
        "acr": "1",
        "realm_access": {
            "roles": ["default-roles-pbench-cli", "offline_access", "uma_authorization"]
        },
        "resource_access": {
            "broker": {"roles": ["read-token"]},
            "account": {
                "roles": ["manage-account", "manage-account-links", "view-profile"]
            },
        },
        "scope": "openid profile email",
        "sid": "1988612e-774d-43b8-8d4a-bbc05ee55edb",
        "email_verified": True,
        "name": user.first_name + " " + user.last_name,
        "preferred_username": username,
        "given_name": user.first_name,
        "family_name": user.last_name,
        "email": user.email,
    }
    if pbench_client_roles:
        payload["resource_access"].update(
            {"pbench-client": {"roles": pbench_client_roles}}
        )
    token_str = jwt.encode(payload, jwt_secret, algorithm="HS256")
    token = ActiveToken(token_str, exp)
    user.add_token(token)
    return token_str


@pytest.fixture(params=[header for header in HeaderTypes])
def build_auth_header(
    request,
    pbench_token,
    pbench_admin_token,
    pbench_token_invalid,
    client,
):
    if request.param == HeaderTypes.VALID_ADMIN:
        header = {"Authorization": "Bearer " + pbench_admin_token}

    elif request.param == HeaderTypes.VALID:
        header = {"Authorization": "Bearer " + pbench_token}

    elif request.param == HeaderTypes.INVALID:
        header = {"Authorization": "Bearer " + pbench_token_invalid}

    elif request.param == HeaderTypes.EMPTY:
        header = {}

    else:
        assert False, f"Unexpected request.param value:  {request.param}"
    return {"header": header, "header_param": request.param}


@pytest.fixture()
def current_user_drb(monkeypatch, create_drb_user, fake_email_validator):
    class FakeHTTPTokenAuth:
        def current_user(self) -> User:
            return create_drb_user

    with monkeypatch.context() as m:
        m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
        yield create_drb_user


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
    metadata = MetadataLog()
    metadata.add_section("pbench")
    metadata.set("pbench", "date", "2002-05-16")
    metadata_file = tmp_path / "metadata.log"
    with metadata_file.open("w") as meta_fp:
        metadata.write(meta_fp)
    with tarfile.open(datafile, "w:xz") as tar:
        tar.add(str(metadata_file), arcname=f"{Dataset.stem(filename)}/metadata.log")
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
