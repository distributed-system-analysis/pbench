from http import HTTPStatus
import itertools

import pytest
import requests

from pbench.server import JSON, PbenchServerConfig
from pbench.server.api.resources import ParamType
from pbench.server.api.resources.datasets_metadata import DatasetsMetadata


class TestDatasetsMetadata:
    @pytest.fixture()
    def query_get_as(self, client, server_config, more_datasets, provide_metadata):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            more_datasets: Dataset construction fixture
            provide_metadata: Dataset metadata fixture
        """

        def query_api(
            payload: JSON, username: str, expected_status: HTTPStatus
        ) -> requests.Response:
            token = self.token(client, server_config, username)
            response = client.get(
                f"{server_config.rest_uri}/datasets/metadata",
                headers={"authorization": f"bearer {token}"},
                query_string=payload,
            )
            assert response.status_code == expected_status

            # We need to log out to avoid "duplicate auth token" errors on the
            # "put" test which does a PUT followed by two GETs.
            client.post(
                f"{server_config.rest_uri}/logout",
                headers={"authorization": f"bearer {token}"},
            )
            return response

        return query_api

    @pytest.fixture()
    def query_put_as(self, client, server_config, more_datasets, provide_metadata):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            more_datasets: Dataset construction fixture
            provide_metadata: Dataset metadata fixture
        """

        def query_api(
            payload: JSON, username: str, expected_status: HTTPStatus
        ) -> requests.Response:
            token = self.token(client, server_config, username)
            response = client.put(
                f"{server_config.rest_uri}/datasets/metadata",
                headers={"authorization": f"bearer {token}"},
                json=payload,
            )
            assert response.status_code == expected_status

            # We need to log out to avoid "duplicate auth token" errors on the
            # test case which does a PUT followed by two GETs.
            client.post(
                f"{server_config.rest_uri}/logout",
                headers={"authorization": f"bearer {token}"},
            )
            return response

        return query_api

    def token(self, client, config: PbenchServerConfig, user: str) -> str:
        response = client.post(
            f"{config.rest_uri}/login",
            json={"username": user, "password": "12345"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.json
        assert data["auth_token"]
        return data["auth_token"]

    def test_get_no_dataset(self, query_get_as):
        response = query_get_as(
            {
                "name": "foobar",
                "metadata": ["dashboard.seen", "dashboard.saved"],
            },
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {"message": "Dataset 'foobar' not found"}

    def test_get_bad_keys(self, query_get_as):
        response = query_get_as(
            {
                "name": "drb",
                "metadata": ["xyzzy", "plugh", "dataset.owner", "dataset.access"],
            },
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {
            "message": "Unrecognized list values ['plugh', 'xyzzy'] given for parameter metadata; expected ['dashboard.*', 'dataset.access', 'dataset.created', 'dataset.owner', 'dataset.uploaded', 'server.deletion', 'user.*']"
        }

    def test_get1(self, query_get_as):
        response = query_get_as(
            {
                "name": "drb",
                "metadata": [
                    "dashboard.seen",
                    "server.deletion",
                    "dataset.access",
                    "user.contact",
                ],
            },
            "drb",
            HTTPStatus.OK,
        )
        assert response.json == {
            "dashboard.seen": None,
            "server.deletion": "2022-12-25",
            "dataset.access": "private",
            "user.contact": "me@example.com",
        }

    def test_get2(self, query_get_as):
        response = query_get_as(
            {
                "name": "drb",
                "metadata": "dashboard.seen,server.deletion,dataset.access,user",
            },
            "drb",
            HTTPStatus.OK,
        )
        assert response.json == {
            "dashboard.seen": None,
            "server.deletion": "2022-12-25",
            "dataset.access": "private",
            "user": {"contact": "me@example.com"},
        }

    def test_get3(self, query_get_as):
        response = query_get_as(
            {
                "name": "drb",
                "metadata": [
                    "dashboard.seen",
                    "server.deletion,dataset.access",
                    "user",
                ],
            },
            "drb",
            HTTPStatus.OK,
        )
        assert response.json == {
            "dashboard.seen": None,
            "server.deletion": "2022-12-25",
            "dataset.access": "private",
            "user": {"contact": "me@example.com"},
        }

    def test_get_unauth(self, query_get_as):
        response = query_get_as(
            {
                "name": "drb",
                "metadata": [
                    "dashboard.seen",
                    "server.deletion,dataset.access",
                    "user",
                ],
            },
            "test",
            HTTPStatus.FORBIDDEN,
        )
        assert (
            response.json["message"]
            == "User test is not authorized to READ a resource owned by drb with private access"
        )

    def test_get_bad_query(self, query_get_as):
        response = query_get_as(
            {
                "name": "drb",
                "controller": "foobar",
                "metadata": "dashboard.seen,server.deletion,dataset.access,user",
            },
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {"message": "Unknown URL query keys: controller"}

    def test_get_bad_query_2(self, query_get_as):
        response = query_get_as(
            {
                "name": "drb",
                "controller": "foobar",
                "plugh": "xyzzy",
                "metadata": ["dashboard.seen", "server.deletion", "dataset.access"],
            },
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {"message": "Unknown URL query keys: controller,plugh"}

    def test_put_missing_json_object(self, client, server_config, pbench_token):
        """
        Test behavior when no JSON payload is given
        """
        response = client.put(f"{server_config.rest_uri}/datasets/metadata")
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"

    def test_put_missing_keys(self, client, server_config, pbench_token):
        """
        Test behavior when JSON payload does not contain all required keys.

        Note that Pbench will silently ignore any additional keys that are
        specified but not required.

        TODO: This is mostly copied from commons.py; ideally these would be
        refactored into a common "superclass" analagous to ApiBase as Commons
        is to ElasticBase.
        """
        classobject = DatasetsMetadata(client.config, client.logger)

        def missing_key_helper(keys):
            response = client.post(
                f"{server_config.rest_uri}/datasets/metadata",
                json=keys,
            )
            assert response.status_code == HTTPStatus.BAD_REQUEST
            missing = sorted(set(required_keys) - set(keys))
            assert (
                response.json.get("message")
                == f"Missing required parameters: {','.join(missing)}"
            )

        parameter_items = classobject.schema.parameters.items()

        required_keys = [
            key for key, parameter in parameter_items if parameter.required
        ]

        all_combinations = []
        for r in range(1, len(parameter_items) + 1):
            for item in itertools.combinations(parameter_items, r):
                tmp_req_keys = [key for key, parameter in item if parameter.required]
                if tmp_req_keys != required_keys:
                    all_combinations.append(item)

        for items in all_combinations:
            keys = {}
            for key, parameter in items:
                if parameter.type is ParamType.ACCESS:
                    keys[key] = "public"
                elif parameter.type is ParamType.DATE:
                    keys[key] = "2020"
                elif parameter.type is ParamType.LIST:
                    keys[key] = []
                elif parameter.type is ParamType.KEYWORD:
                    keys[key] = parameter.keywords[0]
                else:
                    keys[key] = "foobar"

            missing_key_helper(keys)

        # Test in case all of the required keys are missing and some
        # random non-existent key is present in the payload
        if required_keys:
            missing_key_helper({"notakey": None})

    def test_put_no_dataset(self, client, server_config, attach_dataset):
        response = client.put(
            f"{server_config.rest_uri}/datasets/metadata",
            json={
                "controller": "node",
                "name": "foobar",
                "metadata": {"dashboard.seen": True, "dashboard.saved": False},
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {"message": "Dataset 'foobar' not found"}

    def test_put_bad_keys(self, client, server_config, attach_dataset):
        response = client.put(
            f"{server_config.rest_uri}/datasets/metadata",
            json={
                "controller": "node",
                "name": "drb",
                "metadata": {
                    "xyzzy": "private",
                    "what": "sup",
                    "dashboard.saved": True,
                },
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {
            "message": "Unrecognized JSON keys ['what', 'xyzzy'] given for parameter metadata; allowed keywords are ['dashboard.*', 'user.*']"
        }

    def test_put_reserved_metadata(self, client, server_config, attach_dataset):
        response = client.put(
            f"{server_config.rest_uri}/datasets/metadata",
            json={
                "controller": "node",
                "name": "drb",
                "metadata": {"dataset.access": "private"},
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {
            "message": "Unrecognized JSON key ['dataset.access'] given for parameter metadata; allowed keywords are ['dashboard.*', 'user.*']"
        }

    def test_put_nowrite(self, query_get_as, query_put_as):
        response = query_put_as(
            {
                "name": "fio_1",
                "metadata": {"dashboard.seen": False, "dashboard.saved": True},
            },
            "test",
            HTTPStatus.FORBIDDEN,
        )
        assert (
            response.json["message"]
            == "User test is not authorized to UPDATE a resource owned by drb with public access"
        )

    def test_put(self, query_get_as, query_put_as):
        response = query_put_as(
            {
                "name": "drb",
                "metadata": {"dashboard.seen": False, "dashboard.saved": True},
            },
            "drb",
            HTTPStatus.OK,
        )
        assert response.json == {"dashboard.saved": True, "dashboard.seen": False}
        response = query_get_as(
            {
                "name": "drb",
                "metadata": "dashboard,dataset.access",
            },
            "drb",
            HTTPStatus.OK,
        )
        assert response.json == {
            "dashboard": {"saved": True, "seen": False},
            "dataset.access": "private",
        }

        # Try a second GET, returning "dashboard" fields separately:
        response = query_get_as(
            {
                "name": "drb",
                "metadata": ["dashboard.seen", "dashboard.saved", "dataset.access"],
            },
            "drb",
            HTTPStatus.OK,
        )
        assert response.json == {
            "dashboard.saved": True,
            "dashboard.seen": False,
            "dataset.access": "private",
        }
