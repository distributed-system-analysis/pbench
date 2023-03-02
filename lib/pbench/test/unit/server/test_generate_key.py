from http import HTTPStatus

import pytest
import requests


class TestDatasetsAccess:
    @pytest.fixture()
    def query_get_as(self, client, server_config, more_datasets):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            more_datasets: Dataset construction fixture
        """

        def query_api(user_token, expected_status: HTTPStatus) -> requests.Response:
            headers = {"authorization": f"bearer {user_token}"}
            response = client.post(
                f"{server_config.rest_uri}/generate_key",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def test_unauthorized_access(self, query_get_as, pbench_drb_token_invalid):
        response = query_get_as(pbench_drb_token_invalid, HTTPStatus.UNAUTHORIZED)
        assert response.json == {
            "message": "User provided access_token is invalid or expired token"
        }

    def test_successful_api_key_generation(self, query_get_as, pbench_drb_token):
        response = query_get_as(pbench_drb_token, HTTPStatus.OK)
        assert response.json["username"] == "drb"
