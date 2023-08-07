import errno
from http import HTTPStatus
from io import BytesIO
from logging import Logger
from pathlib import Path
from typing import Any, Optional

from flask import Request
import pytest

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources.intake_base import Access, Intake
from pbench.server.api.resources.upload import Upload
from pbench.server.cache_manager import CacheManager, DuplicateTarball
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
    MetadataMissingParameter,
    MetadataSqlError,
)
from pbench.server.database.models.users import User
from pbench.test.unit.server import DRB_USER_ID


class TestUpload:
    cachemanager_created = None
    cachemanager_create_fail = None
    cachemanager_create_path = None
    tarball_deleted = None
    create_metadata = True

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
                    raise TestUpload.cachemanager_create_fail
                self.controllers.append(controller)
                tarball = FakeTarball(path)
                if TestUpload.create_metadata:
                    tarball.metadata = {"pbench": {"date": "2002-05-16T00:00:00"}}
                self.datasets[tarball.name] = tarball
                return tarball

        TestUpload.cachemanager_created = None
        TestUpload.cachemanager_create_fail = None
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
        self, client, caplog, server_config, pbench_drb_token
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
        self, client, caplog, server_config, pbench_drb_token
    ):
        expected_message = "Missing required 'Content-MD5' header value"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_drb_token,
                "Content-MD5": "",
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_missing_filename_extension(
        self, client, caplog, server_config, pbench_drb_token
    ):
        """Test with URL uploading a file named "f" which is missing the
        required filename extension"""
        expected_message = "File extension not supported, must be .tar.xz"
        with BytesIO(b"junk") as f:
            response = client.put(
                f"{server_config.rest_uri}/upload/f",
                data=f,
                headers={
                    "Authorization": "Bearer " + pbench_drb_token,
                    "Content-MD5": "abcde",
                },
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)
        assert not self.cachemanager_created

    def test_missing_length_header_upload(
        self, client, caplog, server_config, pbench_drb_token
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
        self, client, caplog, server_config, pbench_drb_token
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

    @pytest.mark.freeze_time("1970-01-01")
    def test_bad_metadata_upload(self, client, server_config, pbench_drb_token):
        with BytesIO(b"junk") as f:
            response = client.put(
                self.gen_uri(server_config),
                data=f,
                headers={
                    "Authorization": "Bearer " + pbench_drb_token,
                    "Content-MD5": "ANYMD5",
                },
                query_string={
                    "metadata": "global.xyz#A@b=z:y,foobar.badpath:data,server.deletion:3000-12-25T23:59:59+00:00"
                },
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        json = response.json
        assert "errors" in json and "message" in json
        assert json["message"] == "at least one specified metadata key is invalid"
        assert json["errors"] == [
            "Key global.xyz#a@b=z is invalid or isn't settable",
            "Key foobar.badpath is invalid or isn't settable",
            "Metadata key 'server.deletion' value '3000-12-25T23:59:59+00:00' for dataset must be a date/time before 1979-12-30",
        ]
        assert not self.cachemanager_created

    def test_mismatched_md5sum_header(
        self, client, caplog, server_config, pbench_drb_token
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

    @pytest.mark.parametrize(
        "error,http_status,message",
        (
            (errno.ENOSPC, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Out of space on "),
            (
                errno.ENFILE,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Internal Pbench Server Error:",
            ),
            (None, HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Pbench Server Error:"),
        ),
    )
    def test_bad_stream_read(
        self,
        client,
        server_config,
        pbench_drb_token,
        monkeypatch,
        error,
        http_status,
        message,
    ):
        """Test handling of errors from the intake stream read

        The intake code reports errno.ENOSPC with 413/REQUEST_ENTITY_TOO_LARGE,
        but other file create errors are reported as 500/INTERNAL_SERVER_ERROR.
        """
        stream = BytesIO(b"12345")

        def access(self, intake: Intake, request: Request) -> Access:
            return Access(5, stream)

        def read(self):
            if error:
                e = OSError(error, "something went badly")
            else:
                e = Exception("Nobody expects the Spanish Exception")
            raise e

        monkeypatch.setattr(Upload, "_stream", access)
        monkeypatch.setattr(stream, "read", read)

        with BytesIO(b"12345") as data_fp:
            response = client.put(
                self.gen_uri(server_config, "name.tar.xz"),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, "md5sum"),
            )
        assert response.status_code == http_status
        assert response.json.get("message").startswith(message)

    @pytest.mark.parametrize(
        "error,http_status,message",
        (
            (errno.ENOSPC, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Out of space on "),
            (
                errno.ENFILE,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Internal Pbench Server Error:",
            ),
            (None, HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Pbench Server Error:"),
        ),
    )
    def test_md5_failure(
        self,
        monkeypatch,
        client,
        pbench_drb_token,
        server_config,
        tarball,
        error,
        http_status,
        message,
    ):
        """Test handling of errors from MD5 file creation.

        The intake code reports errno.ENOSPC with 413/REQUEST_ENTITY_TOO_LARGE,
        but other file create errors are reported as 500/INTERNAL_SERVER_ERROR.
        """
        path: Optional[Path] = None

        def nogood_write(
            self, data: str, encoding: str = None, errors: str = None
        ) -> int:
            nonlocal path
            path = self
            if error:
                e = OSError(error, "something went badly")
            else:
                e = Exception("Nobody expects the Spanish Exception")
            raise e

        real_unlink = Path.unlink
        unlinks = []

        def record_unlink(self, **kwargs):
            unlinks.append(self.name)
            real_unlink(self, **kwargs)

        datafile, md5_file, md5 = tarball
        monkeypatch.setattr(Path, "write_text", nogood_write)
        monkeypatch.setattr(Path, "unlink", record_unlink)
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
            )
        assert path.name == md5_file.name
        assert md5_file.name in unlinks
        assert datafile.name in unlinks
        assert response.status_code == http_status
        assert response.json.get("message").startswith(message)

    def test_invalid_authorization_upload(
        self, client, caplog, server_config, pbench_drb_token_invalid
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
        self, client, tmp_path, caplog, server_config, pbench_drb_token
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

    def test_temp_exists(
        self, monkeypatch, client, tmp_path, server_config, pbench_drb_token
    ):
        """Test behavior of a conflicting upload

        When the MD5-based temporary intake directory exists already, upload
        will fail with CONFLICT. We want to verify that behavior, and that we
        don't delete the existing directory during cleanup, which could
        interfere with a running upload. This can happen, for example, when a
        large upload times out and the client retries before the original is
        finished.
        """
        md5 = "d41d8cd98f00b204e9800998ecf8427e"
        temp_path: Optional[Path] = None

        def td_exists(self, *args, **kwargs):
            """Mock out Path.mkdir()

            The trick here is that calling the UPLOAD API results in two calls
            to Path.mkdir: one in the __init__ to be sure that ARCHIVE/UPLOAD
            exists, and the second for the temporary subdirectory. We want to
            create both directories, but for the second (MD5-based intake temp)
            we want to raise FileExistsError as if it had already existed, to
            trigger the duplicate upload logic.
            """
            retval = self.real_mkdir(*args, **kwargs)
            if self.name != md5:
                return retval
            nonlocal temp_path
            temp_path = self
            raise FileExistsError(str(self))

        filename = "tmp.tar.xz"
        datafile = tmp_path / filename
        datafile.write_text("compressed tar ball")
        with monkeypatch.context() as m:
            m.setattr(Path, "real_mkdir", Path.mkdir, raising=False)
            m.setattr(Path, "mkdir", td_exists)
            with datafile.open("rb") as data_fp:
                response = client.put(
                    self.gen_uri(server_config, filename),
                    data=data_fp,
                    headers=self.gen_headers(pbench_drb_token, md5),
                )
        assert response.status_code == HTTPStatus.CONFLICT

        # Assert that we captured an intake temporary directory path and that
        # the "duplicate" path wasn't deleted during API cleanup.
        assert temp_path and temp_path.is_dir()
        assert response.json.get("message") == "Dataset is currently being uploaded"
        assert not self.cachemanager_created

    @pytest.mark.parametrize(
        "exception,status",
        (
            (Exception("Test"), HTTPStatus.INTERNAL_SERVER_ERROR),
            (DuplicateTarball("x"), HTTPStatus.BAD_REQUEST),
            (
                OSError(errno.ENOSPC, "The closet is too small!"),
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            ),
            (
                OSError(errno.EACCES, "Can't get they-ah from he-ah"),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            ),
        ),
    )
    def test_upload_cachemanager_error(
        self, client, server_config, pbench_drb_token, tarball, exception, status
    ):
        """
        Cause the CacheManager.create() to fail; this should trigger the cleanup
        actions to delete the tarball, MD5 file, and Dataset, and fail with an
        internal server error.
        """
        datafile, _, md5 = tarball
        TestUpload.cachemanager_create_fail = exception

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
            )

        assert response.status_code == status

        with pytest.raises(DatasetNotFound):
            Dataset.query(resource_id=md5)
        assert self.cachemanager_created
        assert self.cachemanager_create_path
        assert not self.cachemanager_create_path.exists()
        assert not Path(str(self.cachemanager_create_path) + ".md5").exists()

    @pytest.mark.freeze_time("1970-01-01")
    def test_upload(self, client, pbench_drb_token, server_config, tarball):
        """Test a successful dataset upload and validate the metadata and audit
        information.
        """
        datafile, _, md5 = tarball
        name = Dataset.stem(datafile)
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
                query_string={"metadata": "global.pbench.test:data"},
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response.text)
        assert response.json == {
            "message": "File successfully uploaded",
            "name": name,
            "resource_id": md5,
            "notes": [
                "Identified benchmark workload 'unknown'.",
                "Expected expiration date is 1972-01-01.",
            ],
        }
        assert (
            response.headers["location"]
            == f"https://localhost/api/v1/datasets/{md5}/inventory/"
        )

        dataset = Dataset.query(resource_id=md5)
        assert dataset is not None
        assert dataset.resource_id == md5
        assert dataset.name == name
        assert dataset.uploaded.isoformat() == "1970-01-01T00:00:00+00:00"
        assert Metadata.getvalue(dataset, "global") == {"pbench": {"test": "data"}}
        assert Metadata.getvalue(dataset, Metadata.SERVER_DELETION) == "1972-01-02"
        assert Metadata.getvalue(dataset, "dataset.operations") == {
            "INDEX": {"state": "READY", "message": None},
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
        assert audit[0].user_id == DRB_USER_ID
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
        assert audit[1].user_id == DRB_USER_ID
        assert audit[1].user_name == "drb"
        assert audit[1].reason is None
        assert audit[1].attributes == {
            "access": "private",
            "metadata": {"global.pbench.test": "data"},
            "notes": [
                "Identified benchmark workload 'unknown'.",
                "Expected expiration date is 1972-01-01.",
            ],
        }

    @pytest.mark.freeze_time("1970-01-01")
    def test_upload_invalid_metadata(
        self, client, pbench_drb_token, server_config, tarball
    ):
        """Test a dataset upload with a bad metadata. We expect a failure, and
        an 'errors' field in the response JSON explaining each error.

        The metadata processor handles three errors: bad syntax (not k:v), an
        invalid or non-writeabale key value, and a special key value that fails
        validation. We test all three here, and assert that all three errors
        are reported.
        """
        datafile, _, md5 = tarball
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
                query_string={
                    "metadata": "server.archiveonly:abc,dataset.name=test,test.foo:1"
                },
            )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {
            "message": "at least one specified metadata key is invalid",
            "errors": [
                "Metadata key 'server.archiveonly' value 'abc' for dataset must be a boolean",
                "improper metadata syntax dataset.name=test must be 'k:v'",
                "Key test.foo is invalid or isn't settable",
            ],
        }

    @pytest.mark.freeze_time("2023-07-01")
    def test_upload_duplicate(self, client, server_config, pbench_drb_token, tarball):
        datafile, _, md5 = tarball
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response)
        assert response.json == {
            "message": "File successfully uploaded",
            "name": Dataset.stem(datafile),
            "resource_id": md5,
            "notes": [
                "Identified benchmark workload 'unknown'.",
                "Expected expiration date is 2025-06-30.",
            ],
        }
        assert (
            response.headers["location"]
            == f"https://localhost/api/v1/datasets/{md5}/inventory/"
        )

        # Reset manually since we upload twice in this test
        TestUpload.cachemanager_created = None

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
            )

        assert response.status_code == HTTPStatus.OK, repr(response)
        assert response.json == {
            "message": "Dataset already exists",
            "name": Dataset.stem(datafile),
            "resource_id": md5,
        }
        assert (
            response.headers["location"]
            == f"https://localhost/api/v1/datasets/{md5}/inventory/"
        )

        # We didn't get far enough to create a CacheManager
        assert TestUpload.cachemanager_created is None

    def test_upload_metalog_error(
        self, client, monkeypatch, server_config, pbench_drb_token, tarball
    ):
        """Test handling of post-intake error recording metalog

        Cause Metadata.create (which creates the "dataset.metalog" namespace)
        to fail at the very end of the upload so we can test recovery handling.
        """
        datafile, _, md5 = tarball

        def create(**kwargs):
            raise MetadataMissingParameter("dataset")

        monkeypatch.setattr(Metadata, "create", create)

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
        assert audit[0].user_id == DRB_USER_ID
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
        assert audit[1].user_id == DRB_USER_ID
        assert audit[1].user_name == "drb"
        assert audit[1].reason == AuditReason.INTERNAL
        assert (
            audit[1]
            .attributes["message"]
            .startswith("Internal Pbench Server Error: log reference ")
        )

    def test_upload_metadata_error(
        self, client, monkeypatch, server_config, pbench_drb_token, tarball
    ):
        """Test handling of post-intake error setting metadata

        Cause Metadata.setvalue to fail. This should be reported in "failures"
        without failing the upload.
        """
        datafile, _, md5 = tarball

        def setvalue(
            dataset: Dataset, key: str, value: Any, user: Optional[User] = None
        ):
            raise MetadataSqlError("test", dataset, key)

        monkeypatch.setattr(Metadata, "setvalue", setvalue)

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
            )

        assert response.status_code == HTTPStatus.CREATED
        audit = Audit.query()
        assert len(audit) == 2
        fails = audit[1].attributes["failures"]
        assert isinstance(fails, dict)
        assert fails["server.benchmark"].startswith("Error test ")

    @pytest.mark.freeze_time("1970-01-01")
    def test_upload_archive(self, client, pbench_drb_token, server_config, tarball):
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
        assert Metadata.getvalue(dataset, Metadata.SERVER_ARCHIVE) is True
        assert Metadata.getvalue(dataset, Metadata.SERVER_BENCHMARK) == "unknown"
        assert Metadata.getvalue(dataset, Metadata.SERVER_ORIGIN) == "test"
        assert Metadata.getvalue(dataset, Metadata.SERVER_DELETION) == "1972-01-02"
        assert Metadata.getvalue(dataset, "dataset.operations") == {
            "UPLOAD": {"state": "OK", "message": None}
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
        assert audit[0].user_id == DRB_USER_ID
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
        assert audit[1].user_id == DRB_USER_ID
        assert audit[1].user_name == "drb"
        assert audit[1].reason is None
        assert audit[1].attributes == {
            "access": "private",
            "metadata": {"server.archiveonly": True, "server.origin": "test"},
            "notes": [
                "Identified benchmark workload 'unknown'.",
                "Expected expiration date is 1972-01-01.",
                "Indexing is disabled by 'archive only' setting.",
            ],
        }

    @pytest.mark.freeze_time("1970-01-01")
    def test_upload_nometa(self, client, pbench_drb_token, server_config, tarball):
        """Test a successful upload of a dataset without metadata.log."""
        datafile, _, md5 = tarball
        TestUpload.create_metadata = False
        name = Dataset.stem(datafile)
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, datafile.name),
                data=data_fp,
                headers=self.gen_headers(pbench_drb_token, md5),
                query_string={"metadata": "server.origin:test"},
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response.data)
        assert response.json == {
            "message": "File successfully uploaded",
            "name": name,
            "resource_id": md5,
            "notes": [
                f"Results archive is missing '{name}/metadata.log'.",
                "Identified benchmark workload 'unknown'.",
                "Expected expiration date is 1972-01-01.",
                "Indexing is disabled by 'archive only' setting.",
            ],
        }
        assert (
            response.headers["location"]
            == f"https://localhost/api/v1/datasets/{md5}/inventory/"
        )

        dataset = Dataset.query(resource_id=md5)
        assert dataset is not None
        assert dataset.resource_id == md5
        assert dataset.name == name
        assert dataset.uploaded.isoformat() == "1970-01-01T00:00:00+00:00"
        assert Metadata.getvalue(dataset, Metadata.SERVER_ARCHIVE) is True
        assert Metadata.getvalue(dataset, Metadata.SERVER_BENCHMARK) == "unknown"
        assert Metadata.getvalue(dataset, Metadata.SERVER_ORIGIN) == "test"
        assert Metadata.getvalue(dataset, Metadata.SERVER_DELETION) == "1972-01-02"
        assert Metadata.getvalue(dataset, "dataset.operations") == {
            "UPLOAD": {"state": "OK", "message": None}
        }
        assert Metadata.getvalue(dataset, "dataset.metalog") == {
            "pbench": {"name": name, "script": "unknown"}
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
        assert audit[0].user_id == DRB_USER_ID
        assert audit[0].user_name == "drb"
        assert audit[0].reason is None
        assert audit[0].attributes == {
            "access": "private",
            "metadata": {"server.origin": "test"},
        }
        assert audit[1].id == 2
        assert audit[1].root_id == 1
        assert audit[1].operation == OperationCode.CREATE
        assert audit[1].status == AuditStatus.SUCCESS
        assert audit[1].name == "upload"
        assert audit[1].object_type == AuditType.DATASET
        assert audit[1].object_id == md5
        assert audit[1].object_name == name
        assert audit[1].user_id == DRB_USER_ID
        assert audit[1].user_name == "drb"
        assert audit[1].reason is None
        assert audit[1].attributes == {
            "access": "private",
            "metadata": {"server.archiveonly": True, "server.origin": "test"},
            "missing_metadata": True,
            "notes": [
                f"Results archive is missing '{name}/metadata.log'.",
                "Identified benchmark workload 'unknown'.",
                "Expected expiration date is 1972-01-01.",
                "Indexing is disabled by 'archive only' setting.",
            ],
        }
