from http import HTTPStatus
from logging import Logger
from pathlib import Path

from flask import Request
import pytest
import responses

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import ApiParams
from pbench.server.api.resources.intake_base import Intake
from pbench.server.api.resources.relay import Relay
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.audit import (
    Audit,
    AuditReason,
    AuditStatus,
    AuditType,
)
from pbench.server.database.models.datasets import Dataset
from pbench.test.unit.server import DRB_USER_ID


class TestRelay:
    """Test the Relay API.

    This focuses on testing the unique aspects of the _prepare and _access
    methods rather than repeating coverage of all the common base class code.

    In particular, failure of either of the two external GET operations to the
    relay, and problems in the Relay configuration file.
    """

    cachemanager_created = None
    cachemanager_create_fail = None
    cachemanager_create_path = None
    tarball_deleted = None
    create_metadata = True

    @staticmethod
    def gen_uri(server_config, uri="https://relay.example.com/sha256"):
        return f"{server_config.rest_uri}/relay/{uri}"

    def gen_headers(self, auth_token):
        headers = {"Authorization": "Bearer " + auth_token}
        return headers

    @pytest.fixture(scope="function", autouse=True)
    def fake_cache_manager(self, monkeypatch):
        class FakeTarball:
            def __init__(self, path: Path):
                self.tarball_path = path
                self.name = Dataset.stem(path)
                self.metadata = None

            def delete(self):
                TestRelay.tarball_deleted = self.name

        class FakeCacheManager(CacheManager):
            def __init__(self, options: PbenchServerConfig, logger: Logger):
                self.controllers = []
                self.datasets = {}
                TestRelay.cachemanager_created = self

            def create(self, path: Path) -> FakeTarball:
                controller = "ctrl"
                TestRelay.cachemanager_create_path = path
                if TestRelay.cachemanager_create_fail:
                    raise TestRelay.cachemanager_create_fail
                self.controllers.append(controller)
                tarball = FakeTarball(path)
                if TestRelay.create_metadata:
                    tarball.metadata = {"pbench": {"date": "2002-05-16T00:00:00"}}
                self.datasets[tarball.name] = tarball
                return tarball

        TestRelay.cachemanager_created = None
        TestRelay.cachemanager_create_fail = None
        TestRelay.cachemanager_create_path = None
        TestRelay.tarball_deleted = None
        monkeypatch.setattr(CacheManager, "__init__", FakeCacheManager.__init__)
        monkeypatch.setattr(CacheManager, "create", FakeCacheManager.create)

    def test_missing_authorization_header(self, client, server_config):
        """Verify the authorization check"""
        response = client.post(self.gen_uri(server_config))
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert not self.cachemanager_created

    @responses.activate
    def test_relay(self, client, server_config, pbench_drb_token, tarball):
        """Verify the success path

        Ensure successful completion when the primary relay URI returns a valid
        relay manifest referencing a secondary relay URI containing a tarball.
        """
        file, md5file, md5 = tarball
        name = Dataset.stem(file)
        responses.add(
            responses.GET,
            "https://relay.example.com/uri1",
            status=HTTPStatus.OK,
            json={
                "uri": "https://relay.example.com/uri2",
                "name": file.name,
                "md5": md5,
                "access": "private",
                "metadata": ["global.pbench.test:data"],
            },
        )
        responses.add(
            responses.GET,
            "https://relay.example.com/uri2",
            status=HTTPStatus.OK,
            body=file.open("rb"),
            headers={"content-length": f"{file.stat().st_size}"},
            content_type="application/octet-stream",
        )
        response = client.post(
            self.gen_uri(server_config, "https://relay.example.com/uri1"),
            headers=self.gen_headers(pbench_drb_token),
        )
        assert (
            response.status_code == HTTPStatus.CREATED
        ), f"Unexpected result, {response.text}"
        assert response.json == {
            "message": "File successfully uploaded",
            "name": name,
            "resource_id": md5,
        }
        assert (
            response.headers["location"]
            == f"https://localhost/api/v1/datasets/{md5}/inventory/"
        )

        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.CREATE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[0].name == "relay"
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
        assert audit[1].name == "relay"
        assert audit[1].object_type == AuditType.DATASET
        assert audit[1].object_id == md5
        assert audit[1].object_name == Dataset.stem(file)
        assert audit[1].user_id == DRB_USER_ID
        assert audit[1].user_name == "drb"
        assert audit[1].reason is None
        assert audit[1].attributes == {
            "access": "private",
            "metadata": {"global.pbench.test": "data"},
        }

    @responses.activate
    def test_relay_tar_fail(self, client, server_config, pbench_drb_token, tarball):
        """Verify failure when secondary relay URI is not found"""
        file, md5file, md5 = tarball
        responses.add(
            responses.GET,
            "https://relay.example.com/uri1",
            status=HTTPStatus.OK,
            json={
                "uri": "https://relay.example.com/uri2",
                "name": file.name,
                "md5": md5,
                "access": "private",
                "metadata": [],
            },
        )
        responses.add(
            responses.GET, "https://relay.example.com/uri2", status=HTTPStatus.NOT_FOUND
        )
        response = client.post(
            self.gen_uri(server_config, "https://relay.example.com/uri1"),
            headers=self.gen_headers(pbench_drb_token),
        )
        assert (
            response.status_code == HTTPStatus.NOT_FOUND
        ), f"Unexpected result, {response.text}"

        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.CREATE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[0].name == "relay"
        assert audit[0].object_type == AuditType.DATASET
        assert audit[0].object_id == md5
        assert audit[0].object_name == Dataset.stem(file)
        assert audit[0].user_id == DRB_USER_ID
        assert audit[0].user_name == "drb"
        assert audit[0].reason is None
        assert audit[0].attributes == {
            "access": "private",
            "metadata": {},
        }
        assert audit[1].id == 2
        assert audit[1].root_id == 1
        assert audit[1].operation == OperationCode.CREATE
        assert audit[1].status == AuditStatus.FAILURE
        assert audit[1].name == "relay"
        assert audit[1].object_type == AuditType.DATASET
        assert audit[1].object_id == md5
        assert audit[1].object_name == Dataset.stem(file)
        assert audit[1].user_id == DRB_USER_ID
        assert audit[1].user_name == "drb"
        assert audit[1].reason == AuditReason.CONSISTENCY
        assert audit[1].attributes == {
            "message": "Unable to retrieve relay tarball: 'Not Found'"
        }

    @responses.activate
    def test_relay_no_manifest(self, client, server_config, pbench_drb_token):
        """Verify behavior when the primary relay URI isn't found"""
        responses.add(
            responses.GET, "https://relay.example.com/uri1", status=HTTPStatus.NOT_FOUND
        )
        response = client.post(
            self.gen_uri(server_config, "https://relay.example.com/uri1"),
            headers=self.gen_headers(pbench_drb_token),
        )
        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert response.json["message"] == "Relay manifest URI problem: 'Not Found'"

    @responses.activate
    def test_relay_not_json(self, client, server_config, pbench_drb_token):
        """Verify behavior when the primary relay URI doesn't return a JSON
        document.
        """
        responses.add(
            responses.GET,
            "https://relay.example.com/uri1",
            status=HTTPStatus.OK,
            body="This isn't JSON",
        )
        response = client.post(
            self.gen_uri(server_config, "https://relay.example.com/uri1"),
            headers=self.gen_headers(pbench_drb_token),
        )
        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert (
            response.json["message"]
            == "Relay URI did not return a JSON manifest: 'Expecting value: line 1 column 1 (char 0)'"
        )

    @responses.activate
    def test_relay_missing_json_field(self, client, server_config, pbench_drb_token):
        """Verify behavior when the relay manifest doesn't include the
        secondary relay URI field."""
        responses.add(
            responses.GET,
            "https://relay.example.com/uri1",
            status=HTTPStatus.OK,
            json={
                "name": "tarball.tar.xz",
                "md5": "md5",
                "access": "private",
                "metadata": [],
            },
        )
        response = client.post(
            self.gen_uri(server_config, "https://relay.example.com/uri1"),
            headers=self.gen_headers(pbench_drb_token),
        )
        assert response.status_code == HTTPStatus.BAD_GATEWAY
        assert response.json["message"] == "Relay info missing \"'uri'\""

    def test_relay_bad_identify(
        self, client, server_config, pbench_drb_token, monkeypatch
    ):
        """Verify behavior when an unexpected error occurs in the _identify
        helper.
        """

        def throw(self, args: ApiParams, request: Request) -> Intake:
            raise Exception("An exception that's not APIAbort")

        monkeypatch.setattr(Relay, "_identify", throw)
        response = client.post(
            self.gen_uri(server_config, "https://relay.example.com/uri1"),
            headers=self.gen_headers(pbench_drb_token),
        )
        assert (
            response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        ), f"Unexpected result, {response.text}"

    @responses.activate
    def test_relay_bad_stream(
        self, client, server_config, pbench_drb_token, monkeypatch
    ):
        """Verify behavior when an unexpected error occurs in the _stream
        helper.
        """

        def throw(self, args: ApiParams, request: Request) -> Intake:
            raise Exception("An exception that's not APIAbort")

        monkeypatch.setattr(Relay, "_stream", throw)
        responses.add(
            responses.GET,
            "https://relay.example.com/uri1",
            status=HTTPStatus.OK,
            json={
                "name": "tarball.tar.xz",
                "md5": "badmd5",
                "access": "private",
                "metadata": [],
                "uri": "https://relay.example.com/uri2",
            },
        )
        response = client.post(
            self.gen_uri(server_config, "https://relay.example.com/uri1"),
            headers=self.gen_headers(pbench_drb_token),
        )
        assert (
            response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        ), f"Unexpected result, {response.text}"
