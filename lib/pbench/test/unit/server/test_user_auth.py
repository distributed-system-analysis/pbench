import time
import datetime
from pbench.server.database.models.users import User
from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.database.database import Database


def register_user(
    client, server_config, email, username, password, firstname, lastname
):
    return client.post(
        f"{server_config.rest_uri}/register",
        json={
            "email": email,
            "password": password,
            "username": username,
            "first_name": firstname,
            "last_name": lastname,
        },
    )


def login_user(client, server_config, username, password):
    return client.post(
        f"{server_config.rest_uri}/login",
        json={"username": username, "password": password},
    )


class TestUserAuthentication:
    @staticmethod
    def test_registration(client, server_config, pytestconfig):
        client.config["SESSION_FILE_DIR"] = pytestconfig.cache.get("TMP", None)
        """ Test for user registration """
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
            assert response.content_type == "application/json"
            assert response.status_code, 201

    @staticmethod
    def test_registration_missing_fields(client, server_config):
        """ Test for user registration missing fields"""
        with client:
            response = client.post(
                f"{server_config.rest_uri}/register",
                json={
                    "email": "user@domain.com",
                    "password": "12345",
                    "username": "user",
                },
            )
            data = response.json
            assert data["message"] == "Missing firstName field"
            assert response.content_type == "application/json"
            assert response.status_code == 400

    @staticmethod
    def test_registration_email_validity(client, server_config):
        """ Test for validating an email field during registration"""
        with client:
            response = register_user(
                client,
                server_config,
                username="user",
                firstname="firstname",
                lastname="lastName",
                email="user@domain,com",
                password="12345",
            )
            data = response.json
            assert data["message"] == "Invalid email: user@domain,com"
            assert response.content_type == "application/json"
            assert response.status_code == 400

    @staticmethod
    def test_registration_with_registered_user(client, server_config):
        """ Test registration with already registered email"""
        user = User(
            email="user@domain.com",
            password="12345",
            username="user",
            first_name="firstname",
            last_name="lastname",
        )
        Database.db_session.add(user)
        Database.db_session.commit()
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
            assert data["message"] == "Provided username is already in use."
            assert response.content_type == "application/json"
            assert response.status_code == 403

    @staticmethod
    def test_user_login(client, server_config):
        """ Test for login of registered-user login """
        with client:
            # user registration
            resp_register = register_user(
                client,
                server_config,
                username="user",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            data_register = resp_register.json
            assert data_register["message"] == "Successfully registered."
            # registered user login
            response = login_user(client, server_config, "user", "12345")
            data = response.json
            assert data["message"] == "Successfully logged in."
            assert data["auth_token"]
            assert data["username"] == "user"
            assert response.content_type == "application/json"
            assert response.status_code == 200

    @staticmethod
    def test_user_relogin(client, server_config):
        """ Test for login of registered-user login """
        with client:
            # user registration
            resp_register = register_user(
                client,
                server_config,
                username="user",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            data_register = resp_register.json
            assert data_register["message"] == "Successfully registered."
            # registered user login
            response = login_user(client, server_config, "user", "12345")
            data = response.json
            assert data["message"] == "Successfully logged in."
            assert data["auth_token"]
            assert response.content_type == "application/json"
            assert response.status_code == 200

            # Re-login with auth header
            time.sleep(1)
            response = client.post(
                f"{server_config.rest_uri}/login",
                headers=dict(Authorization="Bearer " + data["auth_token"]),
                json={"username": "user", "password": "12345"},
            )
            data = response.json
            assert data["message"] == "Successfully logged in."
            assert response.status_code == 200

            # Re-login without auth header
            time.sleep(1)
            response = client.post(
                f"{server_config.rest_uri}/login",
                json={"username": "user", "password": "12345"},
            )
            data = response.json
            assert data["message"] == "Successfully logged in."
            assert response.status_code == 200

    @staticmethod
    def test_user_login_with_wrong_password(client, server_config):
        """ Test for login of registered-user login """
        with client:
            # user registration
            resp_register = register_user(
                client,
                server_config,
                username="user",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            data_register = resp_register.json
            assert data_register["message"] == "Successfully registered."
            # registered user login
            response = login_user(client, server_config, "user", "123456")
            data = response.json
            assert data["message"] == "Bad login"
            assert response.content_type == "application/json"
            assert response.status_code == 401

    @staticmethod
    def test_login_without_password(client, server_config):
        """ Test for login of non-registered user """
        with client:
            response = client.post(
                f"{server_config.rest_uri}/login", json={"username": "username"},
            )
            data = response.json
            assert data["message"] == "Please provide a valid password"
            assert response.status_code == 400

    @staticmethod
    def test_non_registered_user_login(client, server_config):
        """ Test for login of non-registered user """
        with client:
            response = login_user(client, server_config, "username", "12345")
            data = response.json
            assert data["message"] == "Bad login"
            assert response.status_code == 403

    @staticmethod
    def test_get_user(client, server_config):
        """ Test for get user api"""
        with client:
            resp_register = register_user(
                client,
                server_config,
                username="username",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            data_register = resp_register.json
            assert data_register["message"] == "Successfully registered."

            response = login_user(client, server_config, "username", "12345")
            data_login = response.json
            assert data_login["message"] == "Successfully logged in."
            response = client.get(
                f"{server_config.rest_uri}/user/username",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["data"] is not None
            assert data["data"]["email"] == "user@domain.com"
            assert data["data"]["username"] == "username"
            assert data["data"]["first_name"] == "firstname"
            assert response.status_code == 200

    @staticmethod
    def test_update_user(client, server_config):
        """ Test for get user api"""
        with client:
            resp_register = register_user(
                client,
                server_config,
                username="username",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            data_register = resp_register.json
            assert data_register["message"] == "Successfully registered."

            response = login_user(client, server_config, "username", "12345")
            data_login = response.json
            assert data_login["message"] == "Successfully logged in."

            new_registration_time = datetime.datetime.now()
            response = client.put(
                f"{server_config.rest_uri}/user/username",
                json={"registered_on": new_registration_time, "first_name": "newname"},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert response.status_code == 403
            assert data["message"] == "Invalid update request payload"

            # Test password update
            response = client.put(
                f"{server_config.rest_uri}/user/username",
                json={"password": "newpass"},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert response.status_code == 200
            assert data["data"]["first_name"] == "firstname"
            assert data["data"]["email"] == "user@domain.com"
            time.sleep(1)
            response = login_user(client, server_config, "username", "newpass")
            data_login = response.json
            assert response.status_code == 200
            assert data_login["message"] == "Successfully logged in."

    @staticmethod
    def test_malformed_auth_token(client, server_config):
        """ Test for user status for malformed auth token"""
        with client:
            resp_register = register_user(
                client,
                server_config,
                username="username",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            assert resp_register.json["message"] == "Successfully registered."
            response = client.get(
                f"{server_config.rest_uri}/user/username",
                headers=dict(Authorization="Bearer" + "malformed"),
            )
            data = response.json
            assert data is None

    @staticmethod
    def test_valid_logout(client, server_config):
        """ Test for logout before token expires """
        with client:
            # user registration
            resp_register = register_user(
                client,
                server_config,
                username="user",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            data_register = resp_register.json
            assert data_register["message"] == "Successfully registered."
            # user login
            resp_login = login_user(client, server_config, "user", "12345")
            data_login = resp_login.json
            assert data_login["message"] == "Successfully logged in."
            assert data_login["auth_token"]
            # valid token logout
            response = client.post(
                f"{server_config.rest_uri}/logout",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "Successfully logged out."
            # Check if the token has been successfully removed from the database
            assert (
                not Database.db_session.query(ActiveTokens)
                .filter_by(token=data_login["auth_token"])
                .first()
            )
            assert response.status_code == 200

    @staticmethod
    def test_invalid_logout(client, server_config):
        """ Testing logout after the token expires """
        with client:
            # user registration
            resp_register = register_user(
                client,
                server_config,
                username="username",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            data_register = resp_register.json
            assert data_register["message"] == "Successfully registered."
            assert resp_register.status_code == 201
            # user login
            resp_login = login_user(client, server_config, "username", "12345")
            data_login = resp_login.json
            assert data_login["message"] == "Successfully logged in."
            assert data_login["auth_token"]
            assert resp_login.status_code == 200

            # log out with the current token
            logout_response = client.post(
                f"{server_config.rest_uri}/logout",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert logout_response.json["message"] == "Successfully logged out."

            # invalid token logout
            response = client.post(
                f"{server_config.rest_uri}/logout",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data is None

    @staticmethod
    def test_delete_user(client, server_config):
        """ Test for user status for malformed auth token"""
        with client:
            resp_register = register_user(
                client,
                server_config,
                username="username",
                firstname="firstname",
                lastname="lastName",
                email="user@domain.com",
                password="12345",
            )
            data_register = resp_register.json
            assert data_register["message"] == "Successfully registered."

            # user login
            resp_login = login_user(client, server_config, "username", "12345")
            data_login = resp_login.json
            assert data_login["message"] == "Successfully logged in."
            assert data_login["auth_token"]

            response = client.delete(
                f"{server_config.rest_uri}/user/username",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert data["message"] == "Successfully deleted."
            assert response.status_code == 200
