import datetime
from lib.pbench.test.unit.server.test_user_auth import register_user, login_user


def user_register_login(client, server_config):
    with client:
        response = register_user(
            client,
            server_config,
            username="user",
            firstname="firstname",
            lastname="lastName",
            email="user@domain.com",
            password="12345",
        )
        data = response.json
        assert data["message"] == "Successfully registered."

        response = login_user(client, server_config, "user", "12345")
        data_login = response.json
        assert data_login["auth_token"]
        return data_login


class TestMetadataSession:
    @staticmethod
    def test_metadata_creation_with_authorization(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            # create a favorite session
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config1", "description": "description1"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"

            # create a saved session
            response = client.post(
                f"{server_config.rest_uri}/metadata/saved",
                json={"value": '{"config": "config2", "description": "description2"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"

            # Get all the favorite sessions of logged in user
            response = client.get(
                f"{server_config.rest_uri}/metadata/favorite",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == 200
            data = response.json
            assert data["message"] == "success"
            assert (
                data["data"]["sessions"][0]["value"]
                == '{"config": "config1", "description": "description1"}'
            )

            # Get all the saved sessions of logged in user
            response = client.get(
                f"{server_config.rest_uri}/metadata/saved",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == 200
            data = response.json
            assert data["message"] == "success"
            assert len(data["data"]["sessions"]) == 2

    @staticmethod
    def test_unauthorized_metadata_creation(client, server_config):
        with client:
            # Create a saved session
            response = client.post(
                f"{server_config.rest_uri}/metadata/saved",
                json={"value": '{"config": "config1", "description": "description1"}'},
            )
            data = response.json
            assert data
            assert response.status_code == 201

            # Create a favorite session
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config2", "description": "description2"}'},
            )
            data = response.json
            assert data["message"] == "success"

            # Get all the favorite sessions of non-logged in user
            response = client.get(f"{server_config.rest_uri}/metadata/favorite")
            assert response.status_code == 200
            data = response.json
            assert data["message"] == "success"
            assert (
                data["data"]["sessions"][0]["value"]
                == '{"config": "config2", "description": "description2"}'
            )

            # Get all the saved sessions of non-logged in user
            response = client.get(f"{server_config.rest_uri}/metadata/saved",)
            assert response.status_code == 200
            data = response.json
            assert data["message"] == "success"
            assert len(data["data"]["sessions"]) == 2

    @staticmethod
    def test_single_metadata_query(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config1", "description": "description1"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert response.status_code == 201
            assert data["message"] == "success"
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.get(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"
            assert data["data"]["key"] == "FAVORITE"

    @staticmethod
    def test_unauthorized_metadata_query1(client, server_config):
        # Test querying metadata without Pbench auth header
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config1", "description": "description1"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.get(f"{server_config.rest_uri}/metadata/{metadata_id}",)
            assert response.status_code == 401

    @staticmethod
    def test_unauthorized_metadata_query2(client, server_config):
        # Test querying someone else's metadata
        data_login_1 = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config1", "description": "description1"}'},
                headers=dict(Authorization="Bearer " + data_login_1["auth_token"]),
            )
            data_1 = response.json
            assert data_1["message"] == "success"
            assert data_1["data"]["id"]

            # Create another user and login
            response = register_user(
                client,
                server_config,
                username="user2",
                firstname="firstname2",
                lastname="lastName2",
                email="user2@domain.com",
                password="12345",
            )
            data = response.json
            assert data["message"] == "Successfully registered."

            response = login_user(client, server_config, "user2", "12345")
            data_login_2 = response.json
            assert data_login_2["auth_token"]

            # Create metadata session for 2nd user
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config2", "description": "description2"}'},
                headers=dict(Authorization="Bearer " + data_login_2["auth_token"]),
            )
            data_2 = response.json
            assert data_2["message"] == "success"
            assert data_2["data"]["id"]

            # Query the metadata session id of the 1st user with an auth token of 2nd user
            metadata_id = data_1["data"]["id"]
            response = client.get(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                headers=dict(Authorization="Bearer " + data_login_2["auth_token"]),
            )
            data = response.json
            assert data["message"] == "Not authorized to perform the specified action"
            assert response.status_code == 403

    @staticmethod
    def test_metadata_update(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config1", "description": "description1"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.put(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                json={"value": '{"config": "config1", "description": "description2"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"
            assert (
                data["data"]["value"]
                == '{"config": "config1", "description": "description2"}'
            )

    @staticmethod
    def test_metadata_update_with_invalid_fields(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config1", "description": "description2"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.put(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                json={"created": datetime.datetime.now()},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "Invalid update request payload"
            assert response.status_code == 403

    @staticmethod
    def test_metadata_delete(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata/favorite",
                json={"value": '{"config": "config1", "description": "description2"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.delete(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "success"
            assert response.status_code == 200
