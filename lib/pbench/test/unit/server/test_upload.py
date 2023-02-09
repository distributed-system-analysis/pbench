from http import HTTPStatus
from logging import Logger
from pathlib import Path
import socket
from typing import Any

from freezegun import freeze_time
import pytest

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.audit import (
    Audit,
    AuditReason,
    AuditStatus,
    AuditType,
)
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetNotFound,
    Metadata,
    MetadataKeyError,
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
            "Content-MD5": md5,
            "Content-Type": "application/octet-stream",
        }
        return headers

    @staticmethod
    def verify_logs(caplog):
        for record in caplog.records:
            assert record.levelname not in ("ERROR", "CRITICAL")

    @pytest.fixture(scope="function", autouse=True)
    def fake_cache_manager(self, monkeypatch):
        class FakeTarball:
            def __init__(self, path: Path):
                self.tarball_path = path
                self.name = Dataset.stem(path)
                self.metadata = None

            def delete(self):
                TestUpload.tarball_deleted = self.name

        class FakeCacheManager(CacheManager):
            def __init__(self, options: PbenchServerConfig, logger: Logger):
                self.controllers = []
                self.datasets = {}
                TestUpload.cachemanager_created = self

            def create(self, path: Path) -> FakeTarball:
                controller = "ctrl"
                TestUpload.cachemanager_create_path = path
                if TestUpload.cachemanager_create_fail:
                    raise Exception()
                self.controllers.append(controller)
                tarball = FakeTarball(path)
                tarball.metadata = {"pbench": {"date": "2002-05-16T00:00:00"}}
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

    def test_missing_md5sum_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_drb_token
    ):
        expected_message = "Missing required 'Content-MD5' header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_drb_token,
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_missing_md5sum_header_value(
        self, client, caplog, server_config, setup_ctrl, pbench_drb_token
    ):
        expected_message = "Missing required 'Content-MD5' header value"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_drb_token,
                "controller": self.controller,
                "Content-MD5": "",
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_missing_filename_extension(
        self, client, caplog, server_config, setup_ctrl, pbench_drb_token
    ):
        """Test with URL uploading a file named "f" which is missing the
        required filename extension"""
        expected_message = "File extension not supported, must be .tar.xz"
        response = client.put(
            f"{server_config.rest_uri}/upload/f",
            headers={
                "Authorization": "Bearer " + pbench_drb_token,
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_missing_length_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_drb_token
    ):
        expected_message = "Missing or invalid 'Content-Length' header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_drb_token,
                "Content-MD5": "ANYMD5",
            },
        )
        assert response.status_code == HTTPStatus.LENGTH_REQUIRED
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_bad_length_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_drb_token
    ):
        expected_message = "Missing or invalid 'Content-Length' header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_drb_token,
                "Content-MD5": "ANYMD5",
                "Content-Length": "string",
            },
        )
        assert response.status_code == HTTPStatus.LENGTH_REQUIRED
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_bad_metadata_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_drb_token
    ):
        with freeze_time("1970-01-01 00:42:00"):
            response = client.put(
                self.gen_uri(server_config),
                headers={
                    "Authorization": "Bearer " + pbench_drb_token,
                    "controller": self.controller,
                    "Content-MD5": "ANYMD5",
                    "Content-Length": "STRING",
                },
                query_string={
                    "metadata": "foobar.badpath:data,server.deletion:3000-12-25T23:59:59+00:00"
                },
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        json = response.json
        assert "errors" in json and "message" in json
        assert json["message"] == "at least one specified metadata key is invalid"
        assert json["errors"] == [
            "Key foobar.badpath is invalid or isn't settable",
            "Metadata key 'server.deletion' value '3000-12-25T23:59:59+00:00' for dataset must be a date/time before 1979-12-30",
        ]
        assert not self.cachemanager_created

    def test_mismatched_md5sum_header(
        self, client, caplog, server_config, setup_ctrl, pbench_drb_token
    ):
        filename = "log.tar.xz"
        datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)
        expected_message = "MD5 checksum 9d5a479f6f75fa9b3bab27ef79ad5b29 does not match expected md5sum"
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, filename),
                data=data_fp,
                # Content-Length header set automatically
                headers=self.gen_headers(pbench_drb_token, "md5sum"),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
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
        pbench_drb_token,
    ):
        datafile = tmp_path / bad_extension
        datafile.write_text("compressed tar ball")
        expected_message = "File extension not supported, must be .tar.xz"
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, bad_extension),
                data=data_fp,
                # Content-Length header set automatically
                headers=self.gen_headers(pbench_drb_token, "md5sum"),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_invalid_authorization_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_drb_token_invalid
    ):
        # Upload with invalid token
        response = client.put(
            self.gen_uri(server_config),
            headers=self.gen_headers(pbench_drb_token_invalid, "md5sum"),
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO"]
        assert not self.cachemanager_created

    def test_empty_upload(
        self, client, tmp_path, caplog, server_config, setup_ctrl, pbench_drb_token
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
                    pbench_drb_token, "d41d8cd98f00b204e9800998ecf8427e"
                ),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_upload_cachemanager_error(
        self,
        client,
        caplog,
        server_config,
        setup_ctrl,
        pbench_drb_token,
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
                headers=self.gen_headers(pbench_drb_token, md5),
            )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

        with pytest.raises(DatasetNotFound):
            Dataset.query(resource_id=md5)
        assert self.cachemanager_created
        assert self.cachemanager_create_path
        assert not self.cachemanager_create_path.exists()
        assert not Path(str(self.cachemanager_create_path) + ".md5").exists()

    @pytest.mark.freeze_time("1970-01-01")
    def test_upload(self, client, pbench_drb_token, server_config, setup_ctrl, tarball):
        """Test a successful dataset upload and validate the metadata and audit
        information.
        """
        datafile, _, md5 = tarball
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
                query_string={"metadata": "global.pbench.test:data"},
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response)
        name = Dataset.stem(datafile)

        dataset = Dataset.query(resource_id=md5)
        assert dataset is not None
        assert dataset.resource_id == md5
        assert dataset.name == name
        assert dataset.uploaded.isoformat() == "1970-01-01T00:00:00+00:00"
        assert Metadata.getvalue(dataset, "global") == {"pbench": {"test": "data"}}
        assert Metadata.getvalue(dataset, Metadata.DELETION) == "1972-01-02"
        assert Metadata.getvalue(dataset, "dataset.operations") == {
            "BACKUP": {"state": "READY", "message": None},
            "UNPACK": {"state": "READY", "message": None},
            "UPLOAD": {"state": "OK", "message": None},
        }
        assert self.cachemanager_created
        assert dataset.name in self.cachemanager_created

        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.CREATE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[0].name == "upload"
        assert audit[0].object_type == AuditType.DATASET
        assert audit[0].object_id == md5
        assert audit[0].object_name == name
        assert audit[0].user_id == "3"
        assert audit[0].user_name == "drb"
        assert audit[0].reason is None
        assert audit[0].attributes == {
            "access": "private",
            "metadata": {"global.pbench.test": "data"},
        }
        assert audit[1].id == 2
        assert audit[1].root_id == 1
        assert audit[1].operation == OperationCode.CREATE
        assert audit[1].status == AuditStatus.SUCCESS
        assert audit[1].name == "upload"
        assert audit[1].object_type == AuditType.DATASET
        assert audit[1].object_id == md5
        assert audit[1].object_name == name
        assert audit[1].user_id == "3"
        assert audit[1].user_name == "drb"
        assert audit[1].reason is None
        assert audit[1].attributes == {
            "access": "private",
            "metadata": {"global.pbench.test": "data"},
        }

    @pytest.mark.freeze_time("1970-01-01")
    def test_upload_bad_metadata_syntax(
        self, client, pbench_drb_token, server_config, setup_ctrl, tarball
    ):
        """Test a dataset upload with a bad metadata syntax: we expect k:v."""
        datafile, _, md5 = tarball
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
                query_string={"metadata": "global.pbench.test=data"},
            )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {
            "message": "improper metadata syntax global.pbench.test=data must be 'k:v'"
        }

    def test_upload_duplicate(
        self,
        client,
        caplog,
        server_config,
        setup_ctrl,
        pbench_drb_token,
        tarball,
    ):
        datafile, _, md5 = tarball
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response)

        # Reset manually since we upload twice in this test
        TestUpload.cachemanager_created = None

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
            )

        assert response.status_code == HTTPStatus.OK, repr(response)
        assert response.json.get("message") == "Dataset already exists"

        # We didn't get far enough to create a CacheManager
        assert TestUpload.cachemanager_created is None

    def test_upload_metadata_error(
        self,
        client,
        caplog,
        monkeypatch,
        server_config,
        setup_ctrl,
        pbench_drb_token,
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
                headers=self.gen_headers(pbench_drb_token, md5),
            )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        name = Dataset.stem(datafile)

        with pytest.raises(DatasetNotFound):
            Dataset.query(resource_id=md5)
        assert self.cachemanager_created
        assert self.cachemanager_create_path
        assert not self.cachemanager_create_path.exists()
        assert not Path(str(self.cachemanager_create_path) + ".md5").exists()
        assert self.tarball_deleted == Dataset.stem(datafile)

        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.CREATE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[0].name == "upload"
        assert audit[0].object_type == AuditType.DATASET
        assert audit[0].object_id == md5
        assert audit[0].object_name == name
        assert audit[0].user_id == "3"
        assert audit[0].user_name == "drb"
        assert audit[0].reason is None
        assert audit[0].attributes == {"access": "private", "metadata": {}}
        assert audit[1].id == 2
        assert audit[1].root_id == 1
        assert audit[1].operation == OperationCode.CREATE
        assert audit[1].status == AuditStatus.FAILURE
        assert audit[1].name == "upload"
        assert audit[1].object_type == AuditType.DATASET
        assert audit[1].object_id == md5
        assert audit[1].object_name == name
        assert audit[1].user_id == "3"
        assert audit[1].user_name == "drb"
        assert audit[1].reason == AuditReason.INTERNAL
        assert audit[1].attributes == {"message": "INTERNAL ERROR"}

    @pytest.mark.freeze_time("1970-01-01")
    def test_upload_archive(
        self, client, pbench_drb_token, server_config, setup_ctrl, tarball
    ):
        """Test a successful archiveonly dataset upload."""
        datafile, _, md5 = tarball
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
                query_string={"metadata": "server.archiveonly:t,server.origin:test"},
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response.data)
        name = Dataset.stem(datafile)

        dataset = Dataset.query(resource_id=md5)
        assert dataset is not None
        assert dataset.resource_id == md5
        assert dataset.name == name
        assert dataset.uploaded.isoformat() == "1970-01-01T00:00:00+00:00"
        # assert Metadata.getvalue(dataset, Metadata.ARCHIVEONLY) is True
        assert Metadata.getvalue(dataset, Metadata.ORIGIN) == "test"
        assert Metadata.getvalue(dataset, Metadata.DELETION) == "1972-01-02"
        assert Metadata.getvalue(dataset, "dataset.operations") == {
            "BACKUP": {"state": "READY", "message": None},
            "UPLOAD": {"state": "OK", "message": None},
        }
        assert self.cachemanager_created
        assert dataset.name in self.cachemanager_created

        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.CREATE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[0].name == "upload"
        assert audit[0].object_type == AuditType.DATASET
        assert audit[0].object_id == md5
        assert audit[0].object_name == name
        assert audit[0].user_id == "3"
        assert audit[0].user_name == "drb"
        assert audit[0].reason is None
        assert audit[0].attributes == {
            "access": "private",
            "metadata": {"server.archiveonly": True, "server.origin": "test"},
        }
        assert audit[1].id == 2
        assert audit[1].root_id == 1
        assert audit[1].operation == OperationCode.CREATE
        assert audit[1].status == AuditStatus.SUCCESS
        assert audit[1].name == "upload"
        assert audit[1].object_type == AuditType.DATASET
        assert audit[1].object_id == md5
        assert audit[1].object_name == name
        assert audit[1].user_id == "3"
        assert audit[1].user_name == "drb"
        assert audit[1].reason is None
        assert audit[1].attributes == {
            "access": "private",
            "metadata": {"server.archiveonly": True, "server.origin": "test"},
        }
