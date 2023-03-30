import datetime
from http import HTTPStatus
from typing import Callable, Optional

import dateutil.parser
from flask import Response
from flask.testing import FlaskClient
from freezegun.api import freeze_time
import pytest
import requests

from pbench.server import JSONOBJECT, OperationCode, PbenchServerConfig
from pbench.server.database.models.audit import Audit, AuditReason, AuditStatus
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.users import User


class TestServerAudit:
    audits = []

    @pytest.fixture()
    def query_get(
        self,
        client: FlaskClient,
        server_config: PbenchServerConfig,
        pbench_admin_token: str,
    ):
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
            assert response.status_code == expected_status, response.json["message"]
            return response

        return query_api

    @pytest.fixture()
    def make_audits(
        self,
        client: FlaskClient,
        create_user: User,
        attach_dataset: None,
        query_get: Callable[..., Response],
    ) -> str:
        """Create some audit records to test."""
        user_id = str(create_user.id)
        drb = Dataset.query(name="drb")
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
                dataset=drb,
                user_name="fake",
                status=AuditStatus.BEGIN,
            )
            f.tick(delta=datetime.timedelta(seconds=5))
            Audit.create(
                root=root, status=AuditStatus.FAILURE, reason=AuditReason.PERMISSION
            )
        response = query_get(expected_status=HTTPStatus.OK)
        audits = response.json
        assert audits[0]["status"] == "BEGIN"
        assert audits[0]["operation"] == "CREATE"
        assert audits[0]["name"] == "first"
        assert audits[0]["user_id"] == str(create_user.id)
        assert audits[0]["user_name"] == "test"
        assert audits[0]["object_id"] is None
        assert audits[0]["object_name"] is None
        assert audits[0]["object_type"] is None
        assert audits[0]["user_name"] == "test"
        assert audits[0]["reason"] is None
        assert audits[1]["status"] == "SUCCESS"
        assert audits[1]["operation"] == "CREATE"
        assert audits[1]["name"] == "first"
        assert audits[1]["user_id"] == str(create_user.id)
        assert audits[1]["user_name"] == "test"
        assert audits[1]["object_id"] is None
        assert audits[1]["object_name"] is None
        assert audits[1]["object_type"] is None
        assert audits[1]["reason"] is None
        assert audits[2]["status"] == "BEGIN"
        assert audits[2]["operation"] == "UPDATE"
        assert audits[2]["name"] == "second"
        assert audits[2]["user_id"] is None
        assert audits[2]["user_name"] == "fake"
        assert audits[2]["object_id"] == drb.resource_id
        assert audits[2]["object_name"] == drb.name
        assert audits[2]["object_type"] == "DATASET"
        assert audits[2]["reason"] is None
        assert audits[3]["status"] == "FAILURE"
        assert audits[3]["operation"] == "UPDATE"
        assert audits[3]["name"] == "second"
        assert audits[3]["user_id"] is None
        assert audits[3]["user_name"] == "fake"
        assert audits[3]["object_id"] == drb.resource_id
        assert audits[3]["object_name"] == drb.name
        assert audits[3]["object_type"] == "DATASET"
        assert audits[3]["reason"] == "PERMISSION"

        # The responses are cached so we can avoid repeating the individual
        # fields in subsequent tests.
        TestServerAudit.audits = audits
        return user_id

    def check_audits(self, actual: list[Audit], expected: list[int]):
        assert len(actual) == len(expected)

        for a, e in enumerate(expected):
            assert actual[a] == self.audits[e]

    def test_get_bad_keys(self, query_get: Callable[..., Response]):
        response = query_get({"xyzzy": "foo"}, HTTPStatus.BAD_REQUEST)
        assert response.json == {"message": "Unknown URL query keys: xyzzy"}

    def test_unauthenticated(
        self, query_get: Callable[..., Response], make_audits: str
    ):
        """Verify UNAUTHORIZED status with no authentication token"""
        response = query_get(token=None, expected_status=HTTPStatus.UNAUTHORIZED)
        assert response.json == {
            "message": "Unauthenticated client is not authorized to READ a server administrative resource"
        }

    def test_unauthorized(
        self,
        query_get: Callable[..., Response],
        make_audits: str,
        pbench_drb_token: str,
    ):
        """Verify UNAUTHORIZED status with no authentication token"""
        response = query_get(
            token=pbench_drb_token, expected_status=HTTPStatus.FORBIDDEN
        )
        assert response.json == {
            "message": "User drb is not authorized to READ a server administrative resource"
        }

    def test_get_name(self, query_get: Callable[..., Response], make_audits: str):
        """Get all audit records matching a specific operation name"""
        response = query_get(params={"name": "first"}, expected_status=HTTPStatus.OK)
        audits = response.json
        self.check_audits(audits, [0, 1])

    def test_get_operation(self, query_get: Callable[..., Response], make_audits: str):
        """Get all audit records matching a specific operation"""
        response = query_get(
            params={"operation": "CREATE"}, expected_status=HTTPStatus.OK
        )
        audits = response.json
        self.check_audits(audits, [0, 1])

    def test_get_status_begin(
        self, query_get: Callable[..., Response], make_audits: str
    ):
        """Get all audit records matching a specific status"""
        response = query_get(params={"status": "BEGIN"}, expected_status=HTTPStatus.OK)
        audits = response.json
        self.check_audits(audits, [0, 2])

    def test_get_status_failure(
        self, query_get: Callable[..., Response], make_audits: str
    ):
        """Get all audit records showing a failure"""
        response = query_get(
            params={"status": "FAILURE"}, expected_status=HTTPStatus.OK
        )
        audits = response.json
        self.check_audits(audits, [3])

    def test_get_reason(self, query_get: Callable[..., Response], make_audits: str):
        """Get all audit records showing a failure"""
        response = query_get(
            params={"reason": "PERMISSION"}, expected_status=HTTPStatus.OK
        )
        audits = response.json
        self.check_audits(audits, [3])

    def test_get_start(self, query_get: Callable[..., Response], make_audits: str):
        response = query_get(
            params={"start": dateutil.parser.parse("2022-01-01 01:00:00 UTC")},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [2, 3])

    def test_get_end(self, query_get: Callable[..., Response], make_audits: str):
        response = query_get(
            params={"end": dateutil.parser.parse("2022-01-01 01:00:00 UTC")},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [0, 1])

    def test_get_between(self, query_get: Callable[..., Response], make_audits: str):
        response = query_get(
            params={
                "start": dateutil.parser.parse("2022-01-01 00:00:01 UTC"),
                "end": dateutil.parser.parse("2022-01-01 05:00:02 UTC"),
            },
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [1, 2])

    def test_get_user_name(self, query_get: Callable[..., Response], make_audits: str):
        response = query_get(
            params={"user_name": "test"},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [0, 1])

    def test_get_user_id(self, query_get: Callable[..., Response], make_audits: str):
        response = query_get(
            params={"user_id": "20"},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [0, 1])

    def test_get_object_name(
        self, query_get: Callable[..., Response], make_audits: str
    ):
        response = query_get(
            params={"object_name": "drb"},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [2, 3])

    def test_get_object_id(self, query_get: Callable[..., Response], make_audits: str):
        drb = Dataset.query(name="drb")
        response = query_get(
            params={"object_id": drb.resource_id},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [2, 3])

    def test_get_object_type(
        self, query_get: Callable[..., Response], make_audits: str
    ):
        response = query_get(
            params={"object_type": "DATASET"},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [2, 3])

    def test_get_dataset(self, query_get: Callable[..., Response], make_audits: str):
        drb = Dataset.query(name="drb")
        response = query_get(
            params={"dataset": drb.resource_id},
            expected_status=HTTPStatus.OK,
        )
        audits = response.json
        self.check_audits(audits, [2, 3])
