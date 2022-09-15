from http import HTTPStatus
from logging import Logger
from pathlib import Path
import socket
from typing import Any

import pytest

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetNotFound,
    Metadata,
    MetadataKeyError,
    States,
)


class TestUpload:
    cachemanager_created = None
    cachemanager_create_fail = False
    cachemanager_create_path = None
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
    def verify_logs(caplog, warning_msg):
        found = False
        for record in caplog.records:
            assert record.levelname not in ("ERROR", "CRITICAL")
            if record.levelname == "WARNING" and warning_msg in record.message:
                found = True
        assert found, f"Failed to find expected warning message, {warning_msg!r}"

    @pytest.fixture(scope="function", autouse=True)
    def fake_cache_manager(self, monkeypatch):
        class FakeTarball:
            def __init__(self, path: Path):
                self.tarball_path = path
                self.name = Dataset.stem(path)

            def delete(self):
                TestUpload.tarball_deleted = self.name

            def get_metadata(self):
                return {"pbench": {"date": "2002-05-16T00:00:00"}}

        class FakeCacheManager(CacheManager):
            def __init__(self, options: PbenchServerConfig, logger: Logger):
                self.controllers = []
                self.datasets = {}
                TestUpload.cachemanager_created = self

            def create(self, controller: str, path: Path) -> FakeTarball:
                TestUpload.cachemanager_create_path = path
                if TestUpload.cachemanager_create_fail:
                    raise Exception()
                self.controllers.append(controller)
                tarball = FakeTarball(path)
                self.datasets[tarball.name] = tarball
                return tarball

        TestUpload.cachemanager_created = None
        TestUpload.cachemanager_create_fail = False
        TestUpload.cachemanager_create_path = None
        TestUpload.tarball_deleted = None
        monkeypatch.setattr(CacheManager, "__init__", FakeCacheManager.__init__)
        monkeypatch.setattr(CacheManager, "create", FakeCacheManager.create)

    def test_missing_authorization_header(self, client, server_config):
        response = client.put(self.gen_uri(server_config))
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert not self.cachemanager_created

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
        assert not self.cachemanager_created

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
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created

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
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created

    def test_missing_filename_extension(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        """Test with URL uploading a file named "f" which is missing the
        required filename extension"""
        expected_message = "File extension not supported, must be .tar.xz"
        response = client.put(
            f"{server_config.rest_uri}/upload/f",
            headers={
                "Authorization": "Bearer " + pbench_token,
                "controller": self.controller,
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created

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
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created

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
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created

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
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created

    def test_mismatched_md5sum_header(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        filename = "log.tar.xz"
        datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)
        expected_message = "MD5 checksum 9d5a479f6f75fa9b3bab27ef79ad5b29 does not match expected md5sum"
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, filename),
                data=data_fp,
                # Content-Length header set automatically
                headers=self.gen_headers(pbench_token, "md5sum"),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created
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
        expected_message = "File extension not supported, must be .tar.xz"
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, bad_extension),
                data=data_fp,
                # Content-Length header set automatically
                headers=self.gen_headers(pbench_token, "md5sum"),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created

    def test_invalid_authorization_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token_invalid
    ):
        # Upload with invalid token
        response = client.put(
            self.gen_uri(server_config),
            headers=self.gen_headers(pbench_token_invalid, "md5sum"),
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO"]
        assert not self.cachemanager_created

    def test_empty_upload(
        self, client, tmp_path, caplog, server_config, setup_ctrl, pbench_token
    ):
        filename = "tmp.tar.xz"
        datafile = tmp_path / filename
        datafile.touch()
        expected_message = "'Content-Length' 0 must be greater than 0"
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
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog, expected_message)
        assert not self.cachemanager_created

    def test_upload_cachemanager_error(
        self,
        client,
        caplog,
        server_config,
        setup_ctrl,
        pbench_token,
        tarball,
    ):
        """
        Cause the CacheManager.create() to fail; this should trigger the cleanup
        actions to delete the tarball, MD5 file, and Dataset, and fail with an
        internal server error.
        """
        datafile, _, md5 = tarball
        TestUpload.cachemanager_create_fail = True

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5),
            )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

        with pytest.raises(DatasetNotFound):
            Dataset.query(resource_id=md5)
        assert self.cachemanager_created
        assert self.cachemanager_create_path
        assert not self.cachemanager_create_path.exists()
        assert not Path(str(self.cachemanager_create_path) + ".md5").exists()

    @pytest.mark.freeze_time("1970-01-01")
    def test_upload(
        self,
        caplog,
        freezer,
        client,
        server_config,
        setup_ctrl,
        pbench_token,
        tarball,
    ):
        datafile, _, md5 = tarball
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5),
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response)

        dataset = Dataset.query(resource_id=md5)
        assert dataset is not None
        assert dataset.resource_id == md5
        assert dataset.name == datafile.name[:-7]
        assert dataset.state == States.UPLOADED
        assert dataset.created.isoformat() == "2002-05-16T00:00:00+00:00"
        assert dataset.uploaded.isoformat() == "1970-01-01T00:00:00+00:00"
        assert Metadata.getvalue(dataset, "global") is None
        assert Metadata.getvalue(dataset, Metadata.DELETION) == "1972-01-02"
        assert Metadata.getvalue(dataset, Metadata.OPERATION) == ["BACKUP", "UNPACK"]
        assert self.cachemanager_created
        assert dataset.name in self.cachemanager_created
        audit = Audit.query(operation=OperationCode.CREATE, status=AuditStatus.SUCCESS)
        assert len(audit) == 1
        assert audit[0].object_type == AuditType.DATASET
        assert audit[0].object_id == md5
        assert audit[0].object_name == datafile.name[:-7]
        assert audit[0].user_id == "3"
        assert audit[0].user_name == "drb"

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
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5),
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response)

        # Reset manually since we upload twice in this test
        TestUpload.cachemanager_created = None

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5),
            )

        assert response.status_code == HTTPStatus.OK, repr(response)
        assert response.json.get("message") == "Dataset already exists"

        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO", "WARNING"]

        # We didn't get far enough to create a CacheManager
        assert TestUpload.cachemanager_created is None

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
            Dataset.query(resource_id=md5)
        assert self.cachemanager_created
        assert self.cachemanager_create_path
        assert not self.cachemanager_create_path.exists()
        assert not Path(str(self.cachemanager_create_path) + ".md5").exists()
        assert self.tarball_deleted == Dataset.stem(datafile)

        audit = Audit.query(object_id=md5)
        assert len(audit) == 2
        assert audit[0].operation == OperationCode.CREATE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[1].operation is OperationCode.CREATE
        assert audit[1].status is AuditStatus.FAILURE
