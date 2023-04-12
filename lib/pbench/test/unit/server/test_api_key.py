from http import HTTPStatus

import pytest
import requests

from pbench.server import OperationCode
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType


class TestAPIKey:
    @pytest.fixture()
    def query_get_as(self, client, server_config):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
        """

        def query_api(user_token, expected_status: HTTPStatus) -> requests.Response:
            headers = {"authorization": f"bearer {user_token}"}
            response = client.post(
                f"{server_config.rest_uri}/key",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def test_unauthorized_access(self, query_get_as, pbench_drb_token_invalid):
        response = query_get_as(pbench_drb_token_invalid, HTTPStatus.UNAUTHORIZED)
        assert response.json == {
            "message": "User provided access_token is invalid or expired"
        }
        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.CREATE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[0].name == "apikey"
        assert audit[0].object_type == AuditType.API_KEY
        assert audit[0].object_id is None
        assert audit[0].object_name is None
        assert audit[0].user_id is None
        assert audit[0].user_name is None
        assert audit[0].reason is None
        assert audit[0].attributes is None
        assert audit[1].id == 2
        assert audit[1].root_id == 1
        assert audit[1].operation == OperationCode.CREATE
        assert audit[1].status == AuditStatus.FAILURE
        assert audit[1].name == "apikey"
        assert audit[1].object_type == AuditType.API_KEY
        assert audit[1].object_id is None
        assert audit[1].object_name is None
        assert audit[1].user_id is None
        assert audit[1].user_name is None
        assert audit[1].reason is None
        assert audit[1].attributes is None

    def test_successful_api_key_generation(self, query_get_as, pbench_drb_token):
        response = query_get_as(pbench_drb_token, HTTPStatus.CREATED)
        assert response.json["api_key"]
        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.CREATE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[0].name == "apikey"
        assert audit[0].object_type == AuditType.API_KEY
        assert audit[0].object_id is None
        assert audit[0].object_name is None
        assert audit[0].user_id == "3"
        assert audit[0].user_name == "drb"
        assert audit[0].reason is None
        assert audit[0].attributes is None
        assert audit[1].id == 2
        assert audit[1].root_id == 1
        assert audit[1].operation == OperationCode.CREATE
        assert audit[1].status == AuditStatus.SUCCESS
        assert audit[1].name == "apikey"
        assert audit[1].object_type == AuditType.API_KEY
        assert audit[1].object_id is None
        assert audit[1].object_name is None
        assert audit[1].user_id == "3"
        assert audit[1].user_name == "drb"
        assert audit[1].reason is None
        assert audit[1].attributes["key"]
