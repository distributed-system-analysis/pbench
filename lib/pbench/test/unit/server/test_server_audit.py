from http import HTTPStatus
from typing import Optional

import pytest
import requests

from pbench.server import JSONOBJECT, OperationCode
from pbench.server.database.models.audit import Audit, AuditStatus


class TestServerAudit:
    @pytest.fixture()
    def query_get(self, client, server_config):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
        """

        def query_api(
            params: Optional[JSONOBJECT] = None,
            expected_status: HTTPStatus = HTTPStatus.OK,
        ) -> requests.Response:
            response = client.get(
                f"{server_config.rest_uri}/server/audit", query_string=params
            )
            assert response.status_code == expected_status
            return response

        return query_api

    @pytest.fixture()
    def make_audits(self, db_session, create_user):
        root = Audit.create(
            operation=OperationCode.CREATE,
            name="first",
            user=create_user,
            status=AuditStatus.BEGIN,
        )
        Audit.create(root=root, status=AuditStatus.SUCCESS)

        root = Audit.create(
            operation=OperationCode.UPDATE,
            name="second",
            user_name="fake",
            status=AuditStatus.BEGIN,
        )
        Audit.create(root=root, status=AuditStatus.FAILURE)

    def test_get_bad_keys(self, query_get):
        response = query_get({"xyzzy": "foo"}, HTTPStatus.BAD_REQUEST)
        assert response.json == {"message": "Unknown URL query keys: xyzzy"}

    def test_get_all(self, query_get, make_audits):
        """With no query parameters, we should get all audit records"""
        response = query_get(expected_status=HTTPStatus.OK)
        audits = response.json
        assert len(audits) == 4
        assert audits[0]["status"] == "BEGIN"
        assert audits[1]["status"] == "SUCCESS"
        assert audits[0]["operation"] == audits[1]["operation"] == "CREATE"
        assert audits[0]["name"] == audits[1]["name"] == "first"
        assert audits[0]["user_id"] == audits[1]["user_id"] == "1"
        assert audits[0]["user_name"] == audits[1]["user_name"] == "test"
        assert audits[2]["status"] == "BEGIN"
        assert audits[3]["status"] == "FAILURE"
        assert audits[2]["operation"] == audits[3]["operation"] == "UPDATE"
        assert audits[2]["name"] == audits[3]["name"] == "second"
        assert audits[2]["user_id"] == audits[3]["user_id"] is None
        assert audits[2]["user_name"] == audits[3]["user_name"] == "fake"

    def test_get_name(self, query_get, make_audits):
        """Get all audit records matching a specific operation name"""
        response = query_get(params={"name": "first"}, expected_status=HTTPStatus.OK)
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["status"] == "BEGIN"
        assert audits[1]["status"] == "SUCCESS"
        assert audits[0]["operation"] == audits[1]["operation"] == "CREATE"
        assert audits[0]["name"] == audits[1]["name"] == "first"
        assert audits[0]["user_id"] == audits[1]["user_id"] == "1"
        assert audits[0]["user_name"] == audits[1]["user_name"] == "test"

    def test_get_operation(self, query_get, make_audits):
        """Get all audit records matching a specific operation"""
        response = query_get(
            params={"operation": "CREATE"}, expected_status=HTTPStatus.OK
        )
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["status"] == "BEGIN"
        assert audits[1]["status"] == "SUCCESS"
        assert audits[0]["operation"] == audits[1]["operation"] == "CREATE"
        assert audits[0]["name"] == audits[1]["name"] == "first"
        assert audits[0]["user_id"] == audits[1]["user_id"] == "1"
        assert audits[0]["user_name"] == audits[1]["user_name"] == "test"

    def test_get_status_begin(self, query_get, make_audits):
        """Get all audit records matching a specific status"""
        response = query_get(params={"status": "BEGIN"}, expected_status=HTTPStatus.OK)
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["status"] == audits[1]["status"] == "BEGIN"
        assert audits[0]["operation"] == "CREATE"
        assert audits[1]["operation"] == "UPDATE"
        assert audits[0]["name"] == "first"
        assert audits[1]["name"] == "second"

    def test_get_status_failure(self, query_get, make_audits):
        """Get all audit records showing a failure"""
        response = query_get(
            params={"status": "FAILURE"}, expected_status=HTTPStatus.OK
        )
        audits = response.json
        assert len(audits) == 1
        assert audits[0]["status"] == "FAILURE"
        assert audits[0]["operation"] == "UPDATE"
        assert audits[0]["name"] == "second"
