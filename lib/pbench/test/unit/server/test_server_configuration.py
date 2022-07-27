from http import HTTPStatus

import pytest
import requests


class TestServerConfiguration:
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
            key: str, expected_status: HTTPStatus = HTTPStatus.OK
        ) -> requests.Response:
            k = "" if key is None else f"/{key}"
            response = client.get(f"{server_config.rest_uri}/server/configuration{k}")
            assert response.status_code == expected_status
            return response

        return query_api

    @pytest.fixture()
    def query_put(self, client, server_config, pbench_admin_token):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            pbench_admin_token: Provide an admin authentication token
        """

        def query_api(
            key: str,
            expected_status: HTTPStatus = HTTPStatus.OK,
            token: str = pbench_admin_token,
            **kwargs,
        ) -> requests.Response:
            k = f"/{key}" if key else ""
            response = client.put(
                f"{server_config.rest_uri}/server/configuration{k}",
                headers={"authorization": f"bearer {token}"},
                **kwargs,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def test_get_bad_keys(self, query_get):
        response = query_get("xyzzy", HTTPStatus.BAD_REQUEST)
        assert response.json == {
            "message": "Unrecognized keyword ['xyzzy'] given for parameter key; allowed keywords are ['dataset-lifetime', 'server-banner', 'server-state']"
        }

    def test_get1(self, query_get):
        response = query_get("dataset-lifetime")
        assert response.json == {"dataset-lifetime": "3650"}

    @pytest.mark.parametrize("key", (None, ""))
    def test_get_all(self, query_get, key):
        """
        We use a trailing-slash-insensitive URI mapping so that both
        /server/configuration and /server/configuration/ should be mapped to
        "get all"; test that both paths work.
        """
        response = query_get(key)
        assert response.json == {
            "dataset-lifetime": "3650",
            "server-state": {"status": "enabled"},
            "server-banner": None,
        }

    def test_put_missing_value(self, query_put):
        """
        Test behavior when JSON payload does not contain all required keys.
        """
        response = query_put(
            key="dataset-lifetime", expected_status=HTTPStatus.BAD_REQUEST
        )
        assert (
            response.json.get("message")
            == "No value found for key system configuration key 'dataset-lifetime'"
        )

    def test_put_bad_key(self, query_put):
        response = query_put(key="fookey", expected_status=HTTPStatus.BAD_REQUEST)
        assert response.json == {
            "message": "Unrecognized keyword ['fookey'] given for parameter key; allowed keywords are ['dataset-lifetime', 'server-banner', 'server-state']"
        }

    def test_put_bad_keys(self, query_put):
        response = query_put(
            key=None,
            json={"fookey": "bar"},
            expected_status=HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {
            "message": "Unrecognized configuration parameters ['fookey'] specified: valid parameters are ['dataset-lifetime', 'server-banner', 'server-state']"
        }

    @pytest.mark.parametrize(
        "key,value",
        [
            ("dataset-lifetime", "14 years"),
            ("server-banner", {"banner": None}),
            ("server-state", "running"),
            ("server-state", {"status": "disabled"}),
        ],
    )
    def test_bad_value(self, query_put, key, value):
        response = query_put(
            key=key, expected_status=HTTPStatus.BAD_REQUEST, json={"value": value}
        )
        assert (
            f"Unsupported value for configuration key '{key}'"
            in response.json["message"]
        )

    def test_put_redundant_value(self, query_put):
        response = query_put(
            key="dataset-lifetime",
            query_string={"value": "2"},
            json={"value": "5", "dataset-lifetime": "4"},
            expected_status=HTTPStatus.BAD_REQUEST,
        )
        assert (
            response.json["message"]
            == "Redundant parameters specified in the JSON request body: ['dataset-lifetime', 'value']"
        )

    def test_put_param(self, query_put):
        response = query_put(key="dataset-lifetime", query_string={"value": "2"})
        assert response.json == {"dataset-lifetime": "2"}

    def test_put_value(self, query_put):
        response = query_put(key="dataset-lifetime", json={"value": "2"})
        assert response.json == {"dataset-lifetime": "2"}

    def test_put_value_unauth(self, query_put):
        response = query_put(
            key="dataset-lifetime",
            token="",
            json={"value": "4 days"},
            expected_status=HTTPStatus.UNAUTHORIZED,
        )
        assert response.json == {
            "message": "Unauthenticated client is not authorized to UPDATE a server administrative resource"
        }

    def test_put_value_user(self, query_put, pbench_token):
        response = query_put(
            key="dataset-lifetime",
            token=pbench_token,
            json={"value": "4 days"},
            expected_status=HTTPStatus.FORBIDDEN,
        )
        assert response.json == {
            "message": "User drb is not authorized to UPDATE a server administrative resource"
        }

    def test_put_config(self, query_get, query_put):
        response = query_put(
            key=None,
            json={
                "dataset-lifetime": "2",
                "server-state": {"status": "enabled"},
            },
        )
        assert response.json == {
            "dataset-lifetime": "2",
            "server-state": {"status": "enabled"},
        }
        response = query_get(None)
        assert response.json == {
            "dataset-lifetime": "2",
            "server-state": {"status": "enabled"},
            "server-banner": None,
        }

    def test_disable_api(self, server_config, client, query_put, create_drb_user):
        query_put(
            key="server-state",
            json={
                "value": {
                    "status": "disabled",
                    "message": "Disabled for testing",
                    "contact": "test@example.com",
                }
            },
        )
        response = client.get(f"{server_config.rest_uri}/datasets/list")
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert response.json == {
            "contact": "test@example.com",
            "status": "disabled",
            "message": "Disabled for testing",
        }

    def test_disable_api_readonly(
        self, server_config, client, query_put, pbench_token, more_datasets
    ):
        query_put(
            key="server-state",
            json={
                "value": {
                    "status": "readonly",
                    "message": "Limited for testing",
                    "contact": "test@example.com",
                }
            },
        )
        response = client.get(
            f"{server_config.rest_uri}/datasets/list?owner=drb",
            headers={"authorization": f"Bearer {pbench_token}"},
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json["total"] == 2
        response = client.put(
            f"{server_config.rest_uri}/datasets/metadata/drb",
            headers={"authorization": f"Bearer {pbench_token}"},
            json={"metadata": {"dataset.name": "Test"}},
        )
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert response.json == {
            "status": "readonly",
            "message": "Limited for testing",
            "contact": "test@example.com",
        }
