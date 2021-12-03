from logging import Logger
import socket
from http import HTTPStatus
from pathlib import Path

import pytest

from freezegun import freeze_time

from pbench.server import PbenchServerConfig
from pbench.server.filetree import FileTree
from pbench.server.database.models.datasets import Dataset, States, Metadata
from pbench.test.unit.server.test_user_auth import login_user, register_user


def get_pbench_token(client, server_config):
    # First create a user
    response = register_user(
        client,
        server_config,
        username="user",
        firstname="firstname",
        lastname="lastName",
        email="user@domain.com",
        password="12345",
    )
    assert response.status_code == HTTPStatus.CREATED

    # Login user to get valid pbench token
    response = login_user(client, server_config, "user", "12345")
    assert response.status_code == HTTPStatus.OK
    data = response.json
    assert data["auth_token"]
    return data["auth_token"]


class TestElasticsearch:
    @staticmethod
    def test_missing_json_object(client, caplog, server_config, pbench_token):
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch",
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_empty_url_path(client, caplog, server_config, pbench_token):
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch",
            json={"indices": None},
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Missing required parameters: indices"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_bad_request(client, caplog, server_config, requests_mock, pbench_token):
        requests_mock.post(
            "http://elasticsearch.example.com:7080/some_invalid_url",
            status_code=HTTPStatus.BAD_REQUEST,
        )
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch",
            headers={"Authorization": "Bearer " + pbench_token},
            json={"indices": "some_invalid_url", "payload": '{ "babble": "42" }'},
        )
        assert response.status_code == HTTPStatus.BAD_GATEWAY


class TestGraphQL:
    @staticmethod
    def test_json_object(client, caplog, server_config):
        response = client.post(f"{server_config.rest_uri}/graphql")
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid json object"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"


class TestUpload:
    controller_created = None
    tarball_created = None

    @pytest.fixture
    def setup_ctrl(self):
        self.controller = socket.gethostname()
        yield
        self.controller = None

    @staticmethod
    def gen_uri(server_config, filename="f.tar.xz"):
        return f"{server_config.rest_uri}/upload/{filename}"

    def gen_headers(self, auth_token, md5):
        headers = {
            "Authorization": "Bearer " + auth_token,
            "controller": self.controller,
            "Content-MD5": md5,
        }
        return headers

    @staticmethod
    def verify_logs(caplog):
        for record in caplog.records:
            assert record.levelname not in ("ERROR", "CRITICAL")
        assert caplog.records[-1].levelname == "WARNING"

    @pytest.fixture(scope="function", autouse=True)
    def fake_filetree(self, monkeypatch):
        class FakeTarball:
            def __init__(self, path: Path):
                self.tarball_path = path

        def fake_constructor(self, options: PbenchServerConfig, logger: Logger):
            pass

        def fake_create(self, controller: str, path: Path) -> None:
            TestUpload.controller_created = controller
            TestUpload.tarball_created = path
            return FakeTarball(path)

        TestUpload.controller_created = None
        TestUpload.tarball_created = None
        monkeypatch.setattr(FileTree, "__init__", fake_constructor)
        monkeypatch.setattr(FileTree, "create", fake_create)
        monkeypatch.setattr(FileTree, "__contains__", lambda self, name: False)

    def test_missing_authorization_header(self, client, server_config):
        response = client.put(self.gen_uri(server_config))
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    @pytest.mark.parametrize(
        "malformed_token", ("malformed", "bear token" "Bearer malformed"),
    )
    def test_malformed_authorization_header(
        self, client, server_config, malformed_token
    ):
        response = client.put(
            self.gen_uri(server_config), headers={"Authorization": malformed_token},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_missing_controller_header_upload(
        self, client, caplog, server_config, pbench_token
    ):
        expected_message = "Missing required 'controller' header"
        response = client.put(
            self.gen_uri(server_config),
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)

    def test_missing_md5sum_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        expected_message = "Missing required 'Content-MD5' header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_token,
                "controller": self.controller,
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)

    def test_missing_length_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        expected_message = "Missing required 'Content-Length' header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_token,
                "controller": self.controller,
                "Content-MD5": "ANYMD5",
            },
        )
        assert response.status_code == HTTPStatus.LENGTH_REQUIRED
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)

    def test_mismatched_md5sum_header(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        filename = "log.tar.xz"
        datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, filename),
                data=data_fp,
                # Content-Length header set automatically
                headers=self.gen_headers(pbench_token, "md5sum"),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert (
            response.json.get("message")
            == "MD5 checksum 9d5a479f6f75fa9b3bab27ef79ad5b29 does not match expected md5sum"
        )
        self.verify_logs(caplog)

    @pytest.mark.parametrize("bad_extension", ("test.tar.bad", "test.tar", "test.tar."))
    def test_bad_extension_upload(
        self,
        client,
        bad_extension,
        pytestconfig,
        caplog,
        server_config,
        setup_ctrl,
        pbench_token,
    ):
        tmp_d = pytestconfig.cache.get("TMP", None)
        datafile = Path(tmp_d, bad_extension)
        datafile.write_text("compressed tar ball")
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, bad_extension),
                data=data_fp,
                # Content-Length header set automatically
                headers=self.gen_headers(pbench_token, "md5sum"),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert (
            response.json.get("message")
            == "File extension not supported, must be .tar.xz"
        )
        self.verify_logs(caplog)

    def test_invalid_authorization_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        # Log out the user
        response = client.post(
            f"{server_config.rest_uri}/logout",
            headers={"Authorization": "Bearer " + pbench_token},
        )

        # Upload with invalid token
        response = client.put(
            self.gen_uri(server_config),
            headers=self.gen_headers(pbench_token, "md5sum"),
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO"]

    def test_empty_upload(
        self, client, pytestconfig, caplog, server_config, setup_ctrl, pbench_token
    ):
        filename = "tmp.tar.xz"
        tmp_d = pytestconfig.cache.get("TMP", None)
        datafile = Path(tmp_d, filename)
        datafile.touch()
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, filename),
                data=data_fp,
                # Content-Length header set automatically
                # MD5 hash of an empty file
                headers=self.gen_headers(
                    pbench_token, "d41d8cd98f00b204e9800998ecf8427e"
                ),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert (
            response.json.get("message") == "'Content-Length' 0 must be greater than 0"
        )
        self.verify_logs(caplog)

    def test_upload(
        self,
        client,
        pytestconfig,
        caplog,
        server_config,
        setup_ctrl,
        pbench_token,
        tarball,
    ):
        datafile, _, md5 = tarball
        with datafile.open("rb") as data_fp, freeze_time("1970-01-01"):
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5),
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response)
        tmp_d = pytestconfig.cache.get("TMP", None)
        receive_dir = Path(
            tmp_d, "srv", "pbench", "pbench-move-results-receive", "fs-version-002"
        )
        assert (
            receive_dir.exists()
        ), f"receive_dir = '{receive_dir}', filename = '{datafile.name}'"

        dataset = Dataset.attach(controller=self.controller, path=datafile.name)
        assert dataset is not None
        assert dataset.md5 == md5
        assert dataset.controller == self.controller
        assert dataset.name == datafile.name[:-7]
        assert dataset.state == States.UPLOADED
        assert Metadata.getvalue(dataset, "dashboard") is None
        assert Metadata.getvalue(dataset, Metadata.DELETION) == "1972-01-01"

        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO"]
