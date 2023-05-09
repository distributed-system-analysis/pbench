from http import HTTPStatus
from typing import Optional

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

        def query_api(
            user_token, expected_status: HTTPStatus, label: Optional[str] = "new_key"
        ) -> requests.Response:
            headers = {"authorization": f"bearer {user_token}"}
            payload = {"label": label} if label is not None else {}

            response = client.post(
                f"{server_config.rest_uri}/key",
                headers=headers,
                query_string=payload,
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

    def test_successful_api_key_generation_with_name(
        self, query_post_as, pbench_drb_token
    ):
        response = query_post_as(pbench_drb_token, HTTPStatus.CREATED)
        assert response.json["key"]
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
        assert audit[1].attributes["id"] == response.json["id"]
        assert audit[1].attributes["label"] == response.json["label"]

    def test_successful_api_key_generation_without_label(
        self, query_post_as, pbench_drb_token
    ):
        response = query_post_as(pbench_drb_token, HTTPStatus.CREATED, label=None)
        assert response.json["key"]
        audit = Audit.query()
        assert audit[1].attributes["id"] == response.json["id"]
        assert audit[1].attributes["label"] is None


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

        def query_api_get(
            user_token, expected_status: HTTPStatus, key_id: Optional[str] = None
        ) -> requests.Response:
            headers = {"authorization": f"bearer {user_token}"}
            uri = f"{server_config.rest_uri}/key"
            if key_id:
                uri = uri + f"/{key_id}"
            response = client.get(uri, headers=headers)
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

        assert response.json[0]["username"] == pbench_drb_api_key.user.username
        assert response.json[0]["id"] == pbench_drb_api_key.id
        assert response.json[0]["label"] == pbench_drb_api_key.label
        assert response.json[0]["key"] == pbench_drb_api_key.key
        assert (
            response.json[1]["username"] == pbench_drb_secondary_api_key.user.username
        )
        assert response.json[1]["id"] == pbench_drb_secondary_api_key.id
        assert response.json[1]["label"] == pbench_drb_secondary_api_key.label
        assert response.json[1]["key"] == pbench_drb_secondary_api_key.key

    def test_unauthorized_get(self, query_get_as, pbench_drb_token_invalid):
        response = query_get_as(pbench_drb_token_invalid, HTTPStatus.UNAUTHORIZED)
        assert response.json == {
            "message": "User provided access_token is invalid or expired"
        }

    def test_single_api_key_get(
        self,
        query_get_as,
        pbench_drb_token,
        pbench_drb_api_key,
        pbench_drb_secondary_api_key,
    ):
        response = query_get_as(
            pbench_drb_token, HTTPStatus.OK, pbench_drb_secondary_api_key.id
        )
        assert response.json["key"] == pbench_drb_secondary_api_key.key

    def test_get_single_api_key_notfound(
        self,
        query_get_as,
        pbench_drb_token,
        pbench_invalid_api_key,
        pbench_drb_secondary_api_key,
    ):
        response = query_get_as(
            pbench_drb_token, HTTPStatus.NOT_FOUND, pbench_invalid_api_key
        )
        assert response.json == {"message": "Requested key not found"}

    def test_get_single_api_key_fail(
        self, query_get_as, get_token_func, pbench_drb_api_key, create_user
    ):
        """Accessing api_key that belongs to another user"""

        response = query_get_as(
            get_token_func("test"), HTTPStatus.NOT_FOUND, pbench_drb_api_key.id
        )
        assert response.json == {"message": "Requested key not found"}


class TestAPIKeyDelete:
    @pytest.fixture()
    def query_delete_as(self, client, server_config):
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

    def test_delete_api_key(
        self,
        query_delete_as,
        pbench_drb_token,
        pbench_drb_api_key,
        pbench_drb_secondary_api_key,
    ):

        # we can find it
        keys = APIKey.query(id=pbench_drb_api_key.id)
        key = keys[0]
        assert key.key == pbench_drb_api_key.key
        assert key.id == pbench_drb_api_key.id

        response = query_delete_as(
            pbench_drb_token, pbench_drb_api_key.id, HTTPStatus.OK
        )
        assert response.json == "deleted"
        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.DELETE
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
        assert audit[1].operation == OperationCode.DELETE
        assert audit[1].status == AuditStatus.SUCCESS
        assert audit[1].name == "apikey"
        assert audit[1].object_type == AuditType.API_KEY
        assert audit[1].object_id is None
        assert audit[1].object_name is None
        assert audit[1].user_id == "3"
        assert audit[1].user_name == "drb"
        assert audit[1].reason is None
        assert audit[1].attributes["id"] == pbench_drb_api_key.id
        assert audit[1].attributes["label"] == pbench_drb_api_key.label
        assert APIKey.query(id=pbench_drb_api_key.id) == []
        keys = APIKey.query(id=pbench_drb_secondary_api_key.id)
        assert keys[0].key == pbench_drb_secondary_api_key.key

    def test_unauthorized_delete(
        self, query_delete_as, pbench_drb_token_invalid, pbench_drb_api_key
    ):

        response = query_delete_as(
            pbench_drb_token_invalid,
            pbench_drb_api_key.id,
            HTTPStatus.UNAUTHORIZED,
        )
        assert response.json == {
            "message": "User provided access_token is invalid or expired"
        }
        keys = APIKey.query(id=pbench_drb_api_key.id)
        assert keys[0].id == pbench_drb_api_key.id

    def test_delete_api_key_notfound(
        self, query_delete_as, pbench_drb_token, pbench_invalid_api_key
    ):
        response = query_delete_as(
            pbench_drb_token, pbench_invalid_api_key, HTTPStatus.NOT_FOUND
        )
        assert response.json == {"message": "Requested key not found"}
        audit = Audit.query()
        assert len(audit) == 2
        assert audit[0].id == 1
        assert audit[0].root_id is None
        assert audit[0].operation == OperationCode.DELETE
        assert audit[0].status == AuditStatus.BEGIN
        assert audit[0].name == "apikey"
        assert audit[0].object_type == AuditType.API_KEY
        assert audit[1].id == 2
        assert audit[1].root_id == 1
        assert audit[1].operation == OperationCode.DELETE
        assert audit[1].status == AuditStatus.FAILURE
        assert audit[1].name == "apikey"
        assert audit[1].object_type == AuditType.API_KEY
        assert audit[1].attributes is None

    def test_delete_api_key_fail(
        self, query_delete_as, get_token_func, pbench_drb_api_key, create_user
    ):
        """Deleting api_key that belongs to another user"""

        response = query_delete_as(
            get_token_func("test"), pbench_drb_api_key.id, HTTPStatus.NOT_FOUND
        )
        assert response.json == {"message": "Requested key not found"}
        keys = APIKey.query(id=pbench_drb_api_key.id)
        assert keys[0].id == pbench_drb_api_key.id

    def test_delete_api_key_by_admin(
        self,
        query_delete_as,
        pbench_admin_token,
        pbench_drb_api_key,
        pbench_drb_secondary_api_key,
    ):

        # we can find it
        keys = APIKey.query(id=pbench_drb_api_key.id)
        assert keys[0].id == pbench_drb_api_key.id

        response = query_delete_as(
            pbench_admin_token, pbench_drb_api_key.id, HTTPStatus.OK
        )
        assert response.json == "deleted"
        assert APIKey.query(id=pbench_drb_api_key.id) == []
        keys = APIKey.query(id=pbench_drb_secondary_api_key.id)
        assert keys[0].key == pbench_drb_secondary_api_key.key
