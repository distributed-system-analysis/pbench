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
from urllib.parse import urljoin
import uuid

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from freezegun import freeze_time
import jwt
import pytest
from requests import Response
import responses

from pbench.common import MetadataLog
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.api import create_app
import pbench.server.auth.auth as Auth
from pbench.server.database import init_db
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.template import Template
from pbench.server.database.models.users import User
from pbench.test import on_disk_config
from pbench.test.unit.server import ADMIN_USER_ID, DRB_USER_ID, TEST_USER_ID
from pbench.test.unit.server.headertypes import HeaderTypes

server_cfg_tmpl = """[DEFAULT]
install-dir = {TMP}/opt/pbench-server

[pbench-server]
pbench-top-dir = {TMP}/srv/pbench

[database]
uri = sqlite:///:memory:

[flask-app]
secret-key = my_precious

[elasticsearch]
host = elasticsearch.example.com
port = 7080

[openid-connect]
server_url = http://openid.example.com

[logging]
logger_type = null
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


@pytest.fixture(scope="session")
def server_config(on_disk_server_config) -> PbenchServerConfig:
    """Mock a pbench-server.cfg configuration as defined above.

    Args:
        on_disk_server_config: the on-disk server configuration setup

    Returns:
        a PbenchServerConfig object the test case can use
    """
    cfg_file = on_disk_server_config["cfg_dir"] / "pbench-server.cfg"
    server_config = PbenchServerConfig(str(cfg_file))
    return server_config


@pytest.fixture(scope="session")
def rsa_keys():
    """Fixture for generating an RSA public / private key pair.

    Returns:
        A dictionary containing the RSAPrivateKey object, the PEM encoded public
        key string without the BEGIN/END bookends (mimicing what is returned by
        an OpenID Connect broker), and the PEM encoded public key string with
        the BEGIN/END bookends
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_public_key = (
        private_key.public_key()
        .public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    # Strip "-----BEGIN..." and "-----END...", and the empty element resulting
    # from the trailing newline character.
    public_key_l = pem_public_key.split("\n")[1:-2]
    public_key = "".join(public_key_l)
    return {
        "private_key": private_key,
        "public_key": public_key,
        "pem_public_key": pem_public_key,
    }


@pytest.fixture(scope="session")
def add_auth_connection_mock(server_config, rsa_keys):
    """
    Mocks the OIDC public key GET Requests call on the realm uri.
    Args:
        server_config: Server_config fixture
        rsa_keys: rsa_keys fixture to get te public key
    """
    with responses.RequestsMock() as mock:
        oidc_server = server_config.get("openid-connect", "server_url")
        oidc_realm = server_config.get("openid-connect", "realm")
        url = urljoin(oidc_server, f"realms/{oidc_realm}")

        mock.add(
            responses.GET,
            url,
            status=HTTPStatus.OK,
            json={"public_key": rsa_keys["public_key"]},
        )
        yield mock


@pytest.fixture()
def client(monkeypatch, server_config, add_auth_connection_mock):
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

    with app.app_context():
        yield app_client


@pytest.fixture(scope="session")
def make_logger(server_config):
    """
    Construct a Pbench Logger object
    """
    return get_pbench_logger("TEST", server_config)


@pytest.fixture()
def capinternal(caplog):
    def compare(message: str, response: Optional[Response]):
        uuid_re = r"[a-zA-Z\d]{8}-([a-zA-Z\d]{4}-){3}[a-zA-Z\d]{12}"
        name = r"\w+\s+"
        external = re.compile(f"Internal Pbench Server Error: log reference {uuid_re}")
        internal = re.compile(f"{name}Internal error {uuid_re}: {message}")
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
def db_session(request, server_config, make_logger):
    """
    Construct a temporary DB session for the test case that will reset on
    completion.

    NOTE: the client fixture does something similar, but without the implicit
    cleanup, and with the addition of a Flask context that non-API tests don't
    require. We can't let both initialize the database, or we may lose some
    fixture setup between calls. This fixture will do nothing on load if the
    client fixture is also selected, but we'll still remove the DB afterwards.

    Args:
        request: Access to pytest's request context
        server_config: pbench-server.cfg fixture
        make_logger: produce a Pbench Server logger
    """
    if "client" not in request.fixturenames:
        init_db(server_config, make_logger)
    yield
    Database.db_session.remove()


@pytest.fixture()
def create_user(client) -> User:
    """Construct a test user and add it to the database.

    Args:
        client : Fixture to ensure we have a database
        fake_email_validator : Allow fake email to be used
    """
    user = User(
        id=TEST_USER_ID,
        oidc_id=TEST_USER_ID,
        username="test",
    )
    user.add()
    return user


@pytest.fixture()
def create_admin_user(client) -> User:
    """Construct an admin user and add it to the database.

    Args:
        client : Fixture to ensure we have a database
        fake_email_validator : Allow fake email to be used
    """
    user = User(
        id=ADMIN_USER_ID, oidc_id=ADMIN_USER_ID, username=admin_username, roles="ADMIN"
    )
    user.add()
    return user


@pytest.fixture()
def create_drb_user(client):
    """Construct the "drb" user and add it to the database.

    Args:
        client : Fixture to ensure we have a database
        fake_email_validator : Allow fake email to be used
    """
    drb = User(
        id=DRB_USER_ID,
        oidc_id=DRB_USER_ID,
        username="drb",
    )
    drb.add()
    return drb


@pytest.fixture()
def fake_mtime(monkeypatch):
    """
    Template's init event listener provides the file's modification date to
    support template version control. For unit testing, mock the stat results
    to appear at a fixed time.

    Args:
        monkeypatch: patch fixture
    """

    def fake_stat(_file: str):
        """
        Create a real stat_result using an actual file, but change the st_mtime
        to a known value before returning it.

        Args:
            _file: filename (not used)

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

        Owner   Access  Uploaded    Name
        ------- ------- ----------  ----
        drb     private 2022-01-01  drb
        test    private 1970-01-01  test

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
            owner=str(create_drb_user.username),
            uploaded=datetime.datetime(2022, 1, 1),
            name="drb",
            access="private",
            resource_id="random_md5_string1",
        ).add()
        Dataset(
            owner=str(create_user.username),
            name="test",
            access="private",
            resource_id="random_md5_string2",
        ).add()


@pytest.fixture()
def more_datasets(
    client,
    server_config,
    attach_dataset,
    create_drb_user,
    create_admin_user,
    create_user,
):
    """Supplement the conftest.py "attach_dataset" fixture with a few more
    datasets so we can practice various queries.

    In combination with attach_dataset, the resulting datasets are:

        Owner   Access  Uploaded    Name
        ------- ------- ----------  ----
        drb     private 2022-01-01  drb
        test    private 1970-01-01  test
        drb     public  1978-06-26  fio_1
        test    public  2022-01-01  fio_2
        test    private 1978-06-26  uperf_1
        test    private 1978-06-26  uperf_2
        test    private 1978-06-26  uperf_3
        test    private 1978-06-26  uperf_4

    Args:
        client: Provide a Flask API client
        server_config: Provide a Pbench server configuration
        create_drb_user: Create the "drb" user
        create_admin_user: Create the "test_admin" user
        attach_dataset: Provide some datasets
        create_user: Create the "test" user
    """
    with freeze_time("1978-06-26 08:00:00"):
        Dataset(
            owner=str(create_drb_user.username),
            name="fio_1",
            access="public",
            resource_id="random_md5_string3",
        ).add()
        Dataset(
            owner=str(create_user.username),
            uploaded=datetime.datetime(2022, 1, 1),
            name="fio_2",
            access="public",
            resource_id="random_md5_string4",
        ).add()
        Dataset(
            owner=str(create_user.username),
            name="uperf_1",
            access="private",
            resource_id="random_md5_string5",
        ).add()
        Dataset(
            owner=str(create_user.username),
            name="uperf_2",
            access="private",
            resource_id="random_md5_string6",
        ).add()
        Dataset(
            owner=str(create_user.username),
            name="uperf_3",
            access="private",
            resource_id="random_md5_string7",
        ).add()
        Dataset(
            owner=str(create_user.username),
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
    mapping = {
        "unit-test.v6.run-data.2021-06": [uuid.uuid4().hex],
        "unit-test.v6.run-toc.2021-06": [uuid.uuid4().hex for _ in range(10)],
        "unit-test.v5.result-data-sample.2021-06": [
            uuid.uuid4().hex for _ in range(20)
        ],
    }

    def get_document_map(dataset: Dataset, key: str) -> Metadata:
        assert key == Metadata.INDEX_MAP
        return mapping

    with monkeypatch.context() as m:
        m.setattr(Metadata, "getvalue", get_document_map)
        yield mapping


@pytest.fixture()
def find_template(monkeypatch, fake_mtime):
    """
    Mock a Template class find call to return an object without requiring a DB
    query.

    Args:
        monkeypatch: patching fixture
        fake_mtime: fake file modification time on init
    """

    def fake_find(name: str) -> Optional[Template]:
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
def pbench_admin_token(client, server_config, create_admin_user, rsa_keys):
    """OIDC valid token for the 'ADMIN' user"""
    return generate_token(
        user=create_admin_user,
        private_key=rsa_keys["private_key"],
        client_id=server_config.get("openid-connect", "client"),
        username=admin_username,
        pbench_client_roles=["ADMIN"],
    )


@pytest.fixture()
def pbench_drb_token(client, server_config, create_drb_user, rsa_keys):
    """OIDC valid token for the 'drb' user"""
    return generate_token(
        username="drb",
        client_id=server_config.get("openid-connect", "client"),
        private_key=rsa_keys["private_key"],
        user=create_drb_user,
    )


@pytest.fixture()
def pbench_drb_token_invalid(client, server_config, create_drb_user, rsa_keys):
    """OIDC invalid token for the 'drb' user"""
    return generate_token(
        username="drb",
        private_key=rsa_keys["private_key"],
        client_id=server_config.get("openid-connect", "client"),
        user=create_drb_user,
        valid=False,
    )


@pytest.fixture()
def get_token_func(pbench_admin_token, server_config, rsa_keys):
    """Get the token function for fetching the token for a user

    This fixture yields a function value which can be called to get the internal
    token for the user corresponding to the specified username.

    If the given user is the "Admin" user, then return token generated by the
    pbench_admin_token fixture.  For all other users a new token will be
    generated.
    """
    return lambda user: (
        pbench_admin_token
        if user == admin_username
        else generate_token(
            username=user,
            private_key=rsa_keys["private_key"],
            client_id=server_config.get("openid-connect", "client"),
        )
    )


def generate_token(
    username: str,
    private_key: str,
    client_id: str,
    user: Optional[User] = None,
    pbench_client_roles: Optional[list[str]] = None,
    valid: bool = True,
) -> str:
    """Generates an OIDC JWT token that mimics a real OIDC token
    obtained from the user login.

    Note: The OIDC client id passed as an argument has to match with the
        oidc client id from the default config file. Otherwise the token
        validation will fail in the server code.

    Args:
        username: username to include in the token payload
        private_key: RS256 private key to encode the jwt token
        client_id: OIDC client id to include in the encoded string.
        user: user attributes will be extracted from the user object to include
            in the token payload.
        pbench_client_roles: Any OIDC client specifc roles we want to include
            in the token.
        valid: If True, the generated token will be valid for 10 mins.
            If False, generated token would be invalid and expired

    Returns:
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
        "iat": current_utc,
        "exp": exp,
        "sub": user.oidc_id,
        "aud": client_id,
        "azp": client_id,
        "realm_access": {
            "roles": [
                "default-roles-pbench-server",
                "offline_access",
                "uma_authorization",
            ]
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
        "name": "first_name last_name",
        "preferred_username": username,
        "given_name": "first_name",
        "family_name": "last_name",
        "email": "dummy@esample.com",
    }
    if pbench_client_roles:
        payload["resource_access"].update({client_id: {"roles": pbench_client_roles}})
    token_str = jwt.encode(payload, private_key, algorithm="RS256")
    return token_str


@pytest.fixture(params=[header for header in HeaderTypes])
def build_auth_header(
    request,
    server_config,
    pbench_drb_token,
    pbench_admin_token,
    pbench_drb_token_invalid,
    client,
):
    if request.param == HeaderTypes.VALID_ADMIN:
        header = {"Authorization": "Bearer " + pbench_admin_token}

    elif request.param == HeaderTypes.VALID:
        header = {"Authorization": "Bearer " + pbench_drb_token}

    elif request.param == HeaderTypes.INVALID:
        header = {"Authorization": "Bearer " + pbench_drb_token_invalid}

    elif request.param == HeaderTypes.EMPTY:
        header = {}

    else:
        assert False, f"Unexpected request.param value:  {request.param}"
    return {"header": header, "header_param": request.param}


@pytest.fixture()
def current_user_drb(monkeypatch, create_drb_user):
    class FakeHTTPTokenAuth:
        def current_user(self) -> User:
            return create_drb_user

    with monkeypatch.context() as m:
        m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
        yield create_drb_user


@pytest.fixture()
def current_user_none(monkeypatch):
    class FakeHTTPTokenAuth:
        def current_user(self) -> Optional[User]:
            return None

    with monkeypatch.context() as m:
        m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
        yield None


@pytest.fixture()
def current_user_admin(monkeypatch, create_admin_user):
    class FakeHTTPTokenAuth:
        def current_user(self) -> User:
            return create_admin_user

    with monkeypatch.context() as m:
        m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
        yield create_admin_user


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
