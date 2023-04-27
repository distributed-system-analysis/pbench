from http import HTTPStatus

import pytest
import requests

from pbench.server import OperationCode
from pbench.server.database.models.api_keys import APIKey
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType


class TestPostAPIKey:
    @pytest.fixture()
    def query_post_as(self, client, server_config):
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
                query_string={"name": "new_key"},
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def test_unauthorized_access(self, query_post_as, pbench_drb_token_invalid):
        response = query_post_as(pbench_drb_token_invalid, HTTPStatus.UNAUTHORIZED)
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

    def test_successful_api_key_generation(self, query_post_as, pbench_drb_token):
        response = query_post_as(pbench_drb_token, HTTPStatus.CREATED)
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
        assert audit[1].attributes["key"] == response.json["api_key"]


class TestAPIKeyGet:
    @pytest.fixture()
    def query_get_as(self, client, server_config):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
        """

        def query_api_get(user_token, expected_status: HTTPStatus) -> requests.Response:
            headers = {"authorization": f"bearer {user_token}"}
            response = client.get(
                f"{server_config.rest_uri}/key",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api_get

    def test_successful_api_key_get(
        self,
        query_get_as,
        pbench_drb_token,
        pbench_drb_api_key,
        pbench_drb_secondary_api_key,
    ):

        response = query_get_as(pbench_drb_token, HTTPStatus.OK)

        assert response.json["api_key"]
        assert len(response.json["api_key"]) == 2
        assert "drb_key" in response.json["api_key"]
        assert "secondary_key" in response.json["api_key"]
        assert response.json["api_key"]["drb_key"] == pbench_drb_api_key
        assert response.json["api_key"]["secondary_key"] == pbench_drb_secondary_api_key

    def test_unauthorized_get(self, query_get_as, pbench_drb_token_invalid):
        response = query_get_as(pbench_drb_token_invalid, HTTPStatus.UNAUTHORIZED)
        assert response.json == {
            "message": "User provided access_token is invalid or expired"
        }


class TestAPIKeyDelete:
    @pytest.fixture()
    def query_as(self, client, server_config):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
        """

        def query_api_delete(
            user_token, key, expected_status: HTTPStatus
        ) -> requests.Response:
            headers = {"authorization": f"bearer {user_token}"}
            response = client.delete(
                f"{server_config.rest_uri}/key/{key}",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api_delete

    def test_delete_api_key(self, query_as, pbench_drb_token, pbench_drb_api_key):

        # we can find it
        key = APIKey.query(api_key=pbench_drb_api_key)
        assert key.api_key == pbench_drb_api_key

        query_as(pbench_drb_token, pbench_drb_api_key, HTTPStatus.OK)

        assert APIKey.query(api_key=pbench_drb_api_key) is None

    def test_unauthorized_delete(
        self, query_as, pbench_drb_token_invalid, pbench_drb_api_key
    ):

        response = query_as(
            pbench_drb_token_invalid, pbench_drb_api_key, HTTPStatus.UNAUTHORIZED
        )
        assert response.json == {
            "message": "User provided access_token is invalid or expired"
        }

    def test_delete_api_key_notfound(
        self, query_as, pbench_drb_token, pbench_drb_token_invalid
    ):

        response = query_as(
            pbench_drb_token, pbench_drb_token_invalid, HTTPStatus.NOT_FOUND
        )
        assert response.json == {"message": "Requested key not found"}

    def test_delete_api_key_fail(
        self, query_as, pbench_admin_token, pbench_drb_api_key
    ):

        response = query_as(
            pbench_admin_token, pbench_drb_api_key, HTTPStatus.FORBIDDEN
        )
        assert response.json == {
            "message": "User does not have rights to delete the specified key"
        }
