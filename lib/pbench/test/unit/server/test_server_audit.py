import datetime
from http import HTTPStatus
from typing import Optional

import dateutil.parser
from freezegun.api import freeze_time
import pytest
import requests

from pbench.server import JSONOBJECT, OperationCode
from pbench.server.database.models.audit import Audit, AuditStatus


class TestServerAudit:
    @pytest.fixture()
    def query_get(self, client, server_config, pbench_admin_token):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:

            client: Flask test API client fixture
            server_config: Pbench config fixture
            pbench_admin_token: ADMIN authorization fixture
        """

        def query_api(
            params: Optional[JSONOBJECT] = None,
            expected_status: HTTPStatus = HTTPStatus.OK,
            token: str = pbench_admin_token,
        ) -> requests.Response:
            response = client.get(
                f"{server_config.rest_uri}/server/audit",
                query_string=params,
                headers={"authorization": f"Bearer {token}"},
            )
            assert response.status_code == expected_status
            return response

        return query_api

    @pytest.fixture()
    def make_audits(self, client, create_user) -> str:
        """Create some audit records to test."""
        user_id = str(create_user.id)
        with freeze_time("2022-01-01 00:00:00 UTC") as f:
            root = Audit.create(
                operation=OperationCode.CREATE,
                name="first",
                user=create_user,
                status=AuditStatus.BEGIN,
            )
            f.tick(delta=datetime.timedelta(seconds=2))
            Audit.create(root=root, status=AuditStatus.SUCCESS)

            f.move_to("2022-01-01 05:00:00 UTC")
            root = Audit.create(
                operation=OperationCode.UPDATE,
                name="second",
                user_name="fake",
                status=AuditStatus.BEGIN,
            )
            f.tick(delta=datetime.timedelta(seconds=5))
            Audit.create(root=root, status=AuditStatus.FAILURE)
        return user_id

    def test_get_bad_keys(self, query_get):
        response = query_get({"xyzzy": "foo"}, HTTPStatus.BAD_REQUEST)
        assert response.json == {"message": "Unknown URL query keys: xyzzy"}

    def test_get_all(self, query_get, make_audits):
        """With no query parameters, we should get all audit records"""
        expected_user_id = make_audits
        response = query_get(expected_status=HTTPStatus.OK)
        audits = response.json
        assert len(audits) == 4
        assert audits[0]["status"] == "BEGIN"
        assert audits[0]["operation"] == "CREATE"
        assert audits[0]["name"] == "first"
        assert audits[0]["user_id"] == expected_user_id
        assert audits[0]["user_name"] == "test"
        assert audits[1]["status"] == "SUCCESS"
        assert audits[1]["operation"] == "CREATE"
        assert audits[1]["name"] == "first"
        assert audits[1]["user_id"] == expected_user_id
        assert audits[1]["user_name"] == "test"
        assert audits[2]["status"] == "BEGIN"
        assert audits[2]["operation"] == "UPDATE"
        assert audits[2]["name"] == "second"
        assert audits[2]["user_id"] is None
        assert audits[2]["user_name"] == "fake"
        assert audits[3]["status"] == "FAILURE"
        assert audits[3]["operation"] == "UPDATE"
        assert audits[3]["name"] == "second"
        assert audits[3]["user_id"] is None
        assert audits[3]["user_name"] == "fake"

    def test_unauthenticated(self, query_get, make_audits):
        """Verify UNAUTHORIZED status with no authentication token"""
        response = query_get(token=None, expected_status=HTTPStatus.UNAUTHORIZED)
        assert response.json == {
            "message": "Unauthenticated client is not authorized to READ a server administrative resource"
        }

    def test_unauthorized(self, query_get, make_audits, pbench_drb_token):
        """Verify UNAUTHORIZED status with no authentication token"""
        response = query_get(
            token=pbench_drb_token, expected_status=HTTPStatus.FORBIDDEN
        )
        assert response.json == {
            "message": "User drb is not authorized to READ a server administrative resource"
        }

    def test_get_name(self, query_get, make_audits):
        """Get all audit records matching a specific operation name"""
        response = query_get(params={"name": "first"}, expected_status=HTTPStatus.OK)
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["name"] == "first"
        assert audits[1]["name"] == "first"

    def test_get_operation(self, query_get, make_audits):
        """Get all audit records matching a specific operation"""
        response = query_get(
            params={"operation": "CREATE"}, expected_status=HTTPStatus.OK
        )
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["operation"] == "CREATE"
        assert audits[1]["operation"] == "CREATE"

    def test_get_status_begin(self, query_get, make_audits):
        """Get all audit records matching a specific status"""
        response = query_get(params={"status": "BEGIN"}, expected_status=HTTPStatus.OK)
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["status"] == "BEGIN"
        assert audits[1]["status"] == "BEGIN"

    def test_get_status_failure(self, query_get, make_audits):
        """Get all audit records showing a failure"""
        response = query_get(
            params={"status": "FAILURE"}, expected_status=HTTPStatus.OK
        )
        audits = response.json
        assert len(audits) == 1
        assert audits[0]["status"] == "FAILURE"

    def test_get_status_start(self, query_get, make_audits):
        response = query_get(
            params={"start": dateutil.parser.parse("2022-01-01 01:00:00 UTC")},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["timestamp"] == "2022-01-01T05:00:00+00:00"
        assert audits[1]["timestamp"] == "2022-01-01T05:00:05+00:00"

    def test_get_status_end(self, query_get, make_audits):
        response = query_get(
            params={"end": dateutil.parser.parse("2022-01-01 01:00:00 UTC")},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["timestamp"] == "2022-01-01T00:00:00+00:00"
        assert audits[1]["timestamp"] == "2022-01-01T00:00:02+00:00"

    def test_get_status_between(self, query_get, make_audits):
        response = query_get(
            params={
                "start": dateutil.parser.parse("2022-01-01 00:00:01 UTC"),
                "end": dateutil.parser.parse("2022-01-01 05:00:02 UTC"),
            },
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        assert len(audits) == 2
        assert audits[0]["timestamp"] == "2022-01-01T00:00:02+00:00"
        assert audits[1]["timestamp"] == "2022-01-01T05:00:00+00:00"
