from http import HTTPStatus
import itertools

from pbench.server.api.resources import ParamType
from pbench.server.api.resources.datasets_metadata import DatasetsMetadata


class TestDatasetsMetadata:
    def test_get_no_dataset(self, client, server_config, attach_dataset):
        response = client.get(
            f"{server_config.rest_uri}/datasets/metadata",
            query_string={
                "controller": "node",
                "name": "foobar",
                "metadata": ["dashboard.seen", "dashboard.saved"],
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {"message": "Dataset node>foobar not found"}

    def test_get_bad_keys(self, client, server_config, attach_dataset):
        response = client.get(
            f"{server_config.rest_uri}/datasets/metadata",
            query_string={
                "controller": "node",
                "name": "drb",
                "metadata": ["xyzzy", "plugh", "dataset.owner", "dataset.access"],
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {
            "message": "Unrecognized list values ['plugh', 'xyzzy'] given for parameter metadata; expected ['dashboard.*', 'user.*', 'server.deletion', 'dataset.access', 'dataset.owner']"
        }

    def test_get1(self, client, server_config, provide_metadata):
        response = client.get(
            f"{server_config.rest_uri}/datasets/metadata",
            query_string={
                "controller": "node",
                "name": "drb",
                "metadata": [
                    "dashboard.seen",
                    "server.deletion",
                    "dataset.access",
                    "user.contact",
                ],
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "dashboard.seen": None,
            "server.deletion": "2022-12-25",
            "dataset.access": "private",
            "user.contact": "me@example.com",
        }

    def test_get2(self, client, server_config, provide_metadata):
        response = client.get(
            f"{server_config.rest_uri}/datasets/metadata",
            query_string={
                "controller": "node",
                "name": "drb",
                "metadata": [
                    "dashboard.seen",
                    "server.deletion",
                    "dataset.access",
                    "user",
                ],
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "dashboard.seen": None,
            "server.deletion": "2022-12-25",
            "dataset.access": "private",
            "user": {"contact": "me@example.com"},
        }

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
                f"{server_config.rest_uri}/datasets/metadata", json=keys,
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
        assert response.json == {"message": "Dataset node>foobar not found"}

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

    def test_put(self, client, server_config, provide_metadata):
        response = client.put(
            f"{server_config.rest_uri}/datasets/metadata",
            json={
                "controller": "node",
                "name": "drb",
                "metadata": {
                    "dashboard.seen": False,
                    "dashboard.saved": True,
                    "user.xyzzy": "plugh",
                },
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "dashboard.saved": True,
            "dashboard.seen": False,
            "user.xyzzy": "plugh",
        }
        response = client.get(
            f"{server_config.rest_uri}/datasets/metadata",
            query_string={
                "controller": "node",
                "name": "drb",
                "metadata": [
                    "dashboard.seen",
                    "dashboard.saved",
                    "dataset.access",
                    "user",
                ],
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "dashboard.saved": True,
            "dashboard.seen": False,
            "dataset.access": "private",
            "user": {"contact": "me@example.com", "xyzzy": "plugh"},
        }

        # Try a second GET, returning "user" fields separately:
        response = client.get(
            f"{server_config.rest_uri}/datasets/metadata",
            query_string={
                "controller": "node",
                "name": "drb",
                "metadata": [
                    "dashboard.seen",
                    "dashboard.saved",
                    "dataset.access",
                    "user.contact",
                    "user.xyzzy",
                ],
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "dashboard.saved": True,
            "dashboard.seen": False,
            "dataset.access": "private",
            "user.contact": "me@example.com",
            "user.xyzzy": "plugh",
        }
