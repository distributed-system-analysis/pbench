import datetime
from http import HTTPStatus
import time

from pbench.server.database.database import Database
from pbench.server.database.models.auth_tokens import AuthToken
from pbench.server.database.models.users import User
from pbench.test.unit.server.conftest import admin_username


def register_user(
    client, server_config, email, username, password, firstname, lastname
):
    """
    Helper function to register a user using register API
    """
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


def login_user(client, server_config, username, password, token_expiry=None):
    """
    Helper function to generate a user authentication token
    """
    return client.post(
        f"{server_config.rest_uri}/login",
        json={"username": username, "password": password, "token_expiry": token_expiry},
    )


class TestUserAuthentication:
    @staticmethod
    def test_registration(client, server_config, tmp_path):
        client.config["SESSION_FILE_DIR"] = tmp_path
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
            assert response.content_type == "application/json"
            assert response.status_code, HTTPStatus.CREATED

    @staticmethod
    def test_registration_missing_fields(client, server_config):
        """Test for user registration missing fields"""
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
            assert data["message"] == "Missing first_name field"
            assert response.content_type == "application/json"
            assert response.status_code == HTTPStatus.BAD_REQUEST

    @staticmethod
    def test_registration_email_validity(client, server_config):
        """Test for validating an email field during registration"""
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
            assert response.status_code == HTTPStatus.BAD_REQUEST

    @staticmethod
    def test_registration_with_registered_user(client, server_config):
        """Test registration with already registered email"""
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
            assert response.status_code == HTTPStatus.FORBIDDEN

    @staticmethod
    def test_user_login(client, server_config):
        """Test for login of registered-user login"""
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
            assert resp_register.status_code == HTTPStatus.CREATED
            # registered user login
            response = login_user(client, server_config, "user", "12345")
            data = response.json
            assert data["auth_token"]
            assert data["username"] == "user"
            assert response.content_type == "application/json"
            assert response.status_code == HTTPStatus.OK

    @staticmethod
    def test_user_relogin(client, server_config):
        """Test for login of registered-user login"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            # registered user login
            response = login_user(client, server_config, "user", "12345")
            data = response.json
            assert data["auth_token"]
            assert response.content_type == "application/json"
            assert response.status_code == HTTPStatus.OK

            # Re-login with auth header
            time.sleep(1)
            response = client.post(
                f"{server_config.rest_uri}/login",
                headers=dict(Authorization="Bearer " + data["auth_token"]),
                json={"username": "user", "password": "12345"},
            )
            assert response.status_code == HTTPStatus.OK

            # Re-login without auth header
            time.sleep(1)
            response = client.post(
                f"{server_config.rest_uri}/login",
                json={"username": "user", "password": "12345"},
            )
            assert response.status_code == HTTPStatus.OK

    @staticmethod
    def test_user_login_with_wrong_password(client, server_config):
        """Test for login of registered-user login"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            # registered user login
            response = login_user(client, server_config, "user", "123456")
            data = response.json
            assert data["message"] == "Bad login"
            assert response.content_type == "application/json"
            assert response.status_code == HTTPStatus.UNAUTHORIZED

    @staticmethod
    def test_login_without_password(client, server_config):
        """Test for login of non-registered user"""
        with client:
            response = client.post(
                f"{server_config.rest_uri}/login",
                json={"username": "username"},
            )
            data = response.json
            assert data["message"] == "Please provide a valid password"
            assert response.status_code == HTTPStatus.BAD_REQUEST

    @staticmethod
    def test_non_registered_user_login(client, server_config):
        """Test for login of non-registered user"""
        with client:
            response = login_user(client, server_config, "username", "12345")
            data = response.json
            assert data["message"] == "Bad login"
            assert response.status_code == HTTPStatus.UNAUTHORIZED

    @staticmethod
    def test_get_user(client, server_config):
        """Test for get user api"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            response = login_user(client, server_config, "username", "12345")
            assert response.status_code == HTTPStatus.OK
            data_login = response.json
            response = client.get(
                f"{server_config.rest_uri}/user/username",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert response.status_code == HTTPStatus.OK
            assert data is not None
            assert data["email"] == "user@domain.com"
            assert data["username"] == "username"
            assert data["first_name"] == "firstname"

    @staticmethod
    def test_update_user(client, server_config):
        """Test for get user api"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            response = login_user(client, server_config, "username", "12345")
            assert response.status_code == HTTPStatus.OK
            data_login = response.json

            new_registration_time = datetime.datetime.now()
            response = client.put(
                f"{server_config.rest_uri}/user/username",
                json={"registered_on": new_registration_time, "first_name": "newname"},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == HTTPStatus.FORBIDDEN
            data = response.json
            assert data["message"] == "Invalid update request payload"

            # Test password update
            response = client.put(
                f"{server_config.rest_uri}/user/username",
                json={"password": "newpass"},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            data = response.json
            assert response.status_code == HTTPStatus.OK
            assert data["first_name"] == "firstname"
            assert data["email"] == "user@domain.com"
            time.sleep(1)
            response = login_user(client, server_config, "username", "newpass")
            assert response.status_code == HTTPStatus.OK

    @staticmethod
    def test_external_token_update(client, server_config):
        """Test for external attempt at updating auth token"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            response = login_user(client, server_config, "username", "12345")
            assert response.status_code == HTTPStatus.OK
            data_login = response.json

            response = client.put(
                f"{server_config.rest_uri}/user/username",
                json={"auth_tokens": "external_auth_token"},
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == HTTPStatus.BAD_REQUEST
            data = response.json
            assert data["message"] == "Invalid fields in update request payload"

    @staticmethod
    def test_malformed_auth_token(client, server_config):
        """Test for user status for malformed auth token"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            response = client.get(
                f"{server_config.rest_uri}/user/username",
                headers=dict(Authorization="Bearer" + "malformed"),
            )
            data = response.json
            assert data is None

    @staticmethod
    def test_valid_logout(client, server_config):
        """Test for logout before token expires"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            # user login
            resp_login = login_user(client, server_config, "user", "12345")
            data_login = resp_login.json
            assert data_login["auth_token"]
            # valid token logout
            response = client.post(
                f"{server_config.rest_uri}/logout",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == HTTPStatus.OK
            # Check if the token has been successfully removed from the database
            assert (
                not Database.db_session.query(AuthToken)
                .filter_by(auth_token=data_login["auth_token"])
                .first()
            )
            assert response.status_code == HTTPStatus.OK

    @staticmethod
    def test_invalid_logout(client, server_config):
        """Testing logout after the token expires"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            # user login
            resp_login = login_user(client, server_config, "username", "12345")
            data_login = resp_login.json
            assert resp_login.status_code == HTTPStatus.OK
            assert data_login["auth_token"]

            # log out with the current token
            logout_response = client.post(
                f"{server_config.rest_uri}/logout",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert logout_response.status_code == HTTPStatus.OK

            # Logout using invalid token
            # Expect 200 on response, since the invalid token can not be used anymore
            response = client.post(
                f"{server_config.rest_uri}/logout",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == HTTPStatus.OK

    @staticmethod
    def test_delete_user(client, server_config):
        """Test for user status for malformed auth token"""
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
            assert resp_register.status_code == HTTPStatus.CREATED

            # user login
            resp_login = login_user(client, server_config, "username", "12345")
            data_login = resp_login.json
            assert data_login["auth_token"]

            response = client.delete(
                f"{server_config.rest_uri}/user/username",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == HTTPStatus.OK

    @staticmethod
    def test_non_existent_user_delete(client, server_config):
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
            assert resp_register.status_code == HTTPStatus.CREATED

            # user login
            resp_login = login_user(client, server_config, "username", "12345")
            data_login = resp_login.json
            assert data_login["auth_token"]

            response = client.delete(
                f"{server_config.rest_uri}/user/username1",
                headers=dict(Authorization="Bearer " + data_login["auth_token"]),
            )
            assert response.status_code == HTTPStatus.FORBIDDEN
            assert response.json["message"] == "Not authorized to access user username1"

    @staticmethod
    def test_admin_access(client, server_config, pbench_admin_token):
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
            assert resp_register.status_code == HTTPStatus.CREATED

            # Update user with admin credentials
            response = client.put(
                f"{server_config.rest_uri}/user/username",
                json={"first_name": "newname"},
                headers=dict(Authorization="Bearer " + pbench_admin_token),
            )
            assert response.status_code == HTTPStatus.OK

            # Delete user with admin credentials
            response = client.delete(
                f"{server_config.rest_uri}/user/username",
                headers=dict(Authorization="Bearer " + pbench_admin_token),
            )
            assert response.status_code == HTTPStatus.OK

    @staticmethod
    def test_admin_delete(client, server_config, pbench_admin_token):
        # Delete admin user with admin credentials
        # We should not be able to delete an admin user
        response = client.delete(
            f"{server_config.rest_uri}/user/{admin_username}",
            headers=dict(Authorization="Bearer " + pbench_admin_token),
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json["message"] == "Not authorized to delete user"
