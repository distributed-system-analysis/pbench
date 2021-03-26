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


class TestMetadataObjects:
    @staticmethod
    def test_metadata_creation_with_authorization(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            # create a favorite object
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config1", "description": "description1"}',
                },
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == 201
            data = response.json
            assert data["data"]["key"] == "favorite"

            # create a saved metadata object
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "saved",
                    "value": '{"config": "config2", "description": "description2"}',
                },
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == 201
            data = response.json
            assert data["data"]["key"] == "saved"

            # Get all the favorite metadata objects of logged in user
            response = client.get(
                f"{server_config.rest_uri}/metadata/favorite",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == 200
            data = response.json
            assert (
                data["data"][0]["value"]
                == '{"config": "config1", "description": "description1"}'
            )

            # Get all the saved metadata objects of logged in user
            response = client.get(
                f"{server_config.rest_uri}/metadata/saved",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == 200
            data = response.json
            assert len(data["data"]) == 1

    @staticmethod
    def test_unauthorized_metadata_creation(client, server_config):
        with client:
            # Create a saved object
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "saved",
                    "value": '{"config": "config1", "description": "description1"}',
                },
            )
            assert response.status_code == 401

            # Create a favorite metadata object
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config2", "description": "description2"}',
                },
            )
            assert response.status_code == 401

            # Get all the favorite metadata objects of non-logged in user, should not return any data
            response = client.get(f"{server_config.rest_uri}/metadata/favorite")
            assert response.status_code == 200
            data = response.json
            assert data["data"] == []

            # Get all the saved metadata objects of non-logged in user, should not return any data
            response = client.get(f"{server_config.rest_uri}/metadata/saved",)
            assert response.status_code == 200
            data = response.json
            assert len(data["data"]) == 0

    @staticmethod
    def test_single_metadata_query(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config1", "description": "description1"}',
                },
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert response.status_code == 201
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.get(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["data"]["key"] == "favorite"

    @staticmethod
    def test_unauthorized_metadata_query1(client, server_config):
        # Test querying metadata without Pbench auth header
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config1", "description": "description1"}',
                },
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.get(f"{server_config.rest_uri}/metadata/{metadata_id}",)
            assert response.status_code == 403

    @staticmethod
    def test_unauthorized_metadata_query2(client, server_config):
        # Test querying someone else's metadata
        data_login_1 = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config1", "description": "description1"}',
                },
                headers=dict(Authorization="Bearer " + data_login_1["auth_token"]),
            )
            data_1 = response.json
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

            # Create metadata objects for 2nd user
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config2", "description": "description2"}',
                },
                headers=dict(Authorization="Bearer " + data_login_2["auth_token"]),
            )
            data_2 = response.json
            assert data_2["data"]["id"]

            # Query the metadata object id of the 1st user with an auth token of 2nd user
            metadata_id = data_1["data"]["id"]
            response = client.get(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                headers=dict(Authorization="Bearer " + data_login_2["auth_token"]),
            )
            data = response.json
            assert data["message"] == "Not authorized to get the metadata object"
            assert response.status_code == 403

    @staticmethod
    def test_metadata_update(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config1", "description": "description1"}',
                },
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == 201
            data = response.json
            assert data["data"]["key"] == "favorite"

            metadata_id = data["data"]["id"]
            response = client.put(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                json={"value": '{"config": "config1", "description": "description2"}'},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["data"]["key"] == "favorite"

    @staticmethod
    def test_metadata_update_with_invalid_fields(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config1", "description": "description2"}',
                },
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == 201
            data = response.json
            assert data["data"]["key"] == "favorite"

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
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config1", "description": "description2"}',
                },
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.delete(
                f"{server_config.rest_uri}/metadata/{metadata_id}",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "Metadata object deleted"
            assert response.status_code == 200

    @staticmethod
    def test_publish_metadata_object(client, server_config):
        data_login = user_register_login(client, server_config)
        with client:
            response = client.post(
                f"{server_config.rest_uri}/metadata",
                json={
                    "key": "favorite",
                    "value": '{"config": "config1", "description": "description2"}',
                },
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["data"]["id"]

            metadata_id = data["data"]["id"]
            response = client.post(
                f"{server_config.rest_uri}/metadata/{metadata_id}/publish",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "Metadata object is published"
            assert response.status_code == 200

            # Test if non logged-in user can access this data now
            response = client.get(f"{server_config.rest_uri}/metadata/favorite")
            assert response.status_code == 200
            data = response.json
            assert len(data["data"]) == 1
