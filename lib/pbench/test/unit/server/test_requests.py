import dateutil
from http import HTTPStatus
from logging import Logger
from pathlib import Path
import socket
from typing import Any

from freezegun.api import freeze_time
import pytest

from pbench.server import PbenchServerConfig
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetNotFound,
    MetadataKeyError,
    States,
    Metadata,
)
from pbench.server.filetree import FileTree, Tarball
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
    filetree_created = None
    filetree_create_fail = False
    filetree_create_path = None
    tarball_deleted = None

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
                self.name = Tarball.stem(path)

            def delete(self):
                TestUpload.tarball_deleted = self.name

            def get_metadata(self):
                return {"pbench": {"date": dateutil.parser.parse("2002-05-16")}}

        class FakeFileTree(FileTree):
            def __init__(self, options: PbenchServerConfig, logger: Logger):
                self.controllers = []
                self.datasets = {}
                TestUpload.filetree_created = self

            def create(self, controller: str, path: Path) -> FakeTarball:
                TestUpload.filetree_create_path = path
                if TestUpload.filetree_create_fail:
                    raise Exception()
                self.controllers.append(controller)
                tarball = FakeTarball(path)
                self.datasets[tarball.name] = tarball
                return tarball

        TestUpload.filetree_created = None
        TestUpload.filetree_create_fail = False
        TestUpload.filetree_create_path = None
        TestUpload.tarball_deleted = None
        monkeypatch.setattr(FileTree, "__init__", FakeFileTree.__init__)
        monkeypatch.setattr(FileTree, "create", FakeFileTree.create)

    def test_missing_authorization_header(self, client, server_config):
        response = client.put(self.gen_uri(server_config))
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert not self.filetree_created

    @pytest.mark.parametrize(
        "malformed_token",
        ("malformed", "bear token" "Bearer malformed"),
    )
    def test_malformed_authorization_header(
        self, client, server_config, malformed_token
    ):
        response = client.put(
            self.gen_uri(server_config),
            headers={"Authorization": malformed_token},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert not self.filetree_created

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
        assert not self.filetree_created

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
        assert not self.filetree_created

    def test_missing_length_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        expected_message = "Missing or invalid 'Content-Length' header"
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
        assert not self.filetree_created

    def test_bad_length_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        expected_message = "Missing or invalid 'Content-Length' header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_token,
                "controller": self.controller,
                "Content-MD5": "ANYMD5",
                "Content-Length": "string",
            },
        )
        assert response.status_code == HTTPStatus.LENGTH_REQUIRED
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.filetree_created

    def test_bad_controller_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        expected_message = "Invalid 'controller' header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_token,
                "controller": "not_a_hostname",
                "Content-MD5": "ANYMD5",
                "Content-Length": "STRING",
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.filetree_created

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
        assert not self.filetree_created
        with pytest.raises(DatasetNotFound):
            Dataset.query(name="log")

    @pytest.mark.parametrize("bad_extension", ("test.tar.bad", "test.tar", "test.tar."))
    def test_bad_extension_upload(
        self,
        client,
        bad_extension,
        tmp_path,
        caplog,
        server_config,
        setup_ctrl,
        pbench_token,
    ):
        datafile = tmp_path / bad_extension
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
        assert not self.filetree_created

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
        assert not self.filetree_created

    def test_empty_upload(
        self, client, tmp_path, caplog, server_config, setup_ctrl, pbench_token
    ):
        filename = "tmp.tar.xz"
        datafile = tmp_path / filename
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
        assert not self.filetree_created

    def test_upload_filetree_error(
        self,
        client,
        caplog,
        server_config,
        setup_ctrl,
        pbench_token,
        tarball,
    ):
        """
        Cause the FileTree.create() to fail; this should trigger the cleanup
        actions to delete the tarball, MD5 file, and Dataset, and fail with an
        internal server error.
        """
        datafile, _, md5 = tarball
        TestUpload.filetree_create_fail = True

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5),
            )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

        with pytest.raises(DatasetNotFound):
            Dataset.attach(path=datafile)
        assert self.filetree_created
        assert self.filetree_create_path
        assert not self.filetree_create_path.exists()
        assert not Path(str(self.filetree_create_path) + ".md5").exists()

    def test_upload(
        self,
        client,
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

        dataset = Dataset.query(name=Tarball.stem(datafile))
        assert dataset is not None
        assert dataset.md5 == md5
        assert dataset.controller == self.controller
        assert dataset.name == datafile.name[:-7]
        assert dataset.state == States.UPLOADED
        assert dataset.created == dateutil.parser.parse("2002-05-16")
        assert dataset.uploaded == dateutil.parser.parse("1970-01-01")
        assert Metadata.getvalue(dataset, "dashboard") is None
        assert Metadata.getvalue(dataset, Metadata.DELETION) == "1972-01-01"
        assert self.filetree_created
        assert dataset.name in self.filetree_created

        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO"]

    def test_upload_duplicate(
        self,
        client,
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

        # Reset manually since we upload twice in this test
        TestUpload.filetree_created = None

        with datafile.open("rb") as data_fp, freeze_time("1970-01-01"):
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5),
            )

        assert response.status_code == HTTPStatus.OK, repr(response)
        assert response.json.get("message") == "Dataset already exists"

        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO", "WARNING"]

        # We didn't get far enough to create a FileTree
        assert TestUpload.filetree_created is None

    def test_upload_duplicate_diff_md5(
        self,
        client,
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

        # Reset manually since we upload twice in this test
        TestUpload.filetree_created = None

        OTHER_MD5 = "NOT_THE_MD5_YOURE_LOOKING_FOR"
        with datafile.open("rb") as data_fp, freeze_time("1970-01-01"):
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers={
                    "Authorization": "Bearer " + pbench_token,
                    "controller": self.controller,
                    "Content-MD5": OTHER_MD5,
                },
            )

        assert response.status_code == HTTPStatus.CONFLICT, repr(response)
        assert (
            response.json.get("message")
            == f"Duplicate dataset has different MD5 ({md5} != {OTHER_MD5})"
        )

        for record in caplog.records:
            assert record.levelname in ["WARNING", "DEBUG", "INFO"]

        # We didn't get far enough to create a FileTree
        assert TestUpload.filetree_created is None

    def test_upload_metadata_error(
        self,
        client,
        caplog,
        monkeypatch,
        server_config,
        setup_ctrl,
        pbench_token,
        tarball,
    ):
        """
        Cause the Metadata.setvalue to fail at the very end of the upload so we
        can test recovery handling.
        """
        datafile, _, md5 = tarball

        def setvalue(dataset: Dataset, key: str, value: Any):
            raise MetadataKeyError()

        monkeypatch.setattr(Metadata, "setvalue", setvalue)

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5),
            )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

        with pytest.raises(DatasetNotFound):
            Dataset.attach(path=datafile)
        assert self.filetree_created
        assert self.filetree_create_path
        assert not self.filetree_create_path.exists()
        assert not Path(str(self.filetree_create_path) + ".md5").exists()
        assert self.tarball_deleted == Tarball.stem(datafile)
