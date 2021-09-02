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
                "metadata": ["seen", "saved"],
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
                "metadata": ["xyzzy", "plugh", "owner", "access"],
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {
            "message": "Unrecognized list values ['xyzzy', 'plugh'] given for parameter metadata; expected saved,seen,user,deletion,access,owner"
        }

    def test_get(self, client, server_config, provide_metadata):
        response = client.get(
            f"{server_config.rest_uri}/datasets/metadata",
            query_string={
                "controller": "node",
                "name": "drb",
                "metadata": ["seen", "saved", "access", "user"],
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "saved": False,
            "seen": True,
            "access": "private",
            "user": {"contact": "me@example.com"},
        }

    def test_put_missing_json_object(self, client, server_config, pbench_token):
        """
        Test behavior when no JSON payload is given
        """
        response = client.put(f"{server_config.rest_uri}/datasets/metadata")
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"

    def test_put_missing_keys(self, client, server_config, user_ok, pbench_token):
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
                "metadata": {"seen": True, "saved": False},
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
                "metadata": {"xyzzy": "private", "what": "sup", "saved": True},
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {
            "message": "Unrecognized JSON keys what,xyzzy given for parameter metadata; allowed keywords are saved,seen,user"
        }

    def test_put_reserved_metadata(self, client, server_config, attach_dataset):
        response = client.put(
            f"{server_config.rest_uri}/datasets/metadata",
            json={
                "controller": "node",
                "name": "drb",
                "metadata": {"access": "private"},
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json == {
            "message": "Unrecognized JSON keys access given for parameter metadata; allowed keywords are saved,seen,user"
        }

    def test_put(self, client, server_config, provide_metadata):
        response = client.put(
            f"{server_config.rest_uri}/datasets/metadata",
            json={
                "controller": "node",
                "name": "drb",
                "metadata": {"seen": False, "saved": True, "user": {"xyzzy": "plugh"}},
            },
        )
        assert response.status_code == HTTPStatus.OK
        response = client.get(
            f"{server_config.rest_uri}/datasets/metadata",
            query_string={
                "controller": "node",
                "name": "drb",
                "metadata": ["seen", "saved", "access", "user"],
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "saved": True,
            "seen": False,
            "access": "private",
            "user": {"xyzzy": "plugh"},
        }
