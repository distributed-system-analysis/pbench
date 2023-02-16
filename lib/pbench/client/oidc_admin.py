from http import HTTPStatus
import os

import requests

from pbench.server.auth import Connection


class OIDCAdmin(Connection):
    OIDC_REALM = os.getenv("OIDC_REALM", "pbench-server")
    ADMIN_USERNAME = os.getenv("OIDC_ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("OIDC_ADMIN_PASSWORD", "admin")

    def __init__(self, server_url: str):
        super().__init__(server_url, verify=False)

    def get_admin_token(self) -> dict:
        """pbench-server realm admin user login.

        Returns:
            access_token json payload

            { 'access_token': <access_token>,
              'expires_in': 60, 'refresh_expires_in': 1800,
              'refresh_token': <refresh_token>,
              'token_type': 'Bearer',
              'not-before-policy': 0,
              'session_state': '8f558797-50e7-496d-bb45-3b5ac9fdcddb',
              'scope': 'profile email'}

        """
        url_path = "/realms/master/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": self.ADMIN_USERNAME,
            "password": self.ADMIN_PASSWORD,
        }
        return self.post(path=url_path, data=data).json()

    def create_new_user(
        self,
        username: str,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
    ) -> requests.Response:
        """Creates a new user under the OIDC_REALM.

        Note: This involves a REST API call to the
        OIDC server to create a new user.

        Args:
            username: username to register,
            email: user email address,
            password: user password,
            first_name: Optional first name of the user,
            last_name: Optional first name of the user,

        Returns:
            Response from the request.
        """
        admin_token = self.get_admin_token().get("access_token")
        url_path = f"/admin/realms/{self.OIDC_REALM}/users"
        headers = {"Authorization": f"Bearer {admin_token}"}
        data = {
            "username": username,
            "email": email,
            "emailVerified": True,
            "enabled": True,
            "firstName": first_name,
            "lastName": last_name,
            "credentials": [
                {"type": "password", "value": password, "temporary": False}
            ],
        }
        response = self.post(path=url_path, json=data, headers=headers)
        return response

    def user_login(self, client_id: str, username: str, password: str) -> dict:
        """pbench-server realm user login on a specified client.

        Args:
            client_id: client_name to use in the request
            username: username of the user logging in
            password: OIDC password

        Returns:
            access_token json payload

            { 'access_token': <access_token>,
              'expires_in': 60, 'refresh_expires_in': 1800,
              'refresh_token': <refresh_token>,
              'token_type': 'Bearer',
              'not-before-policy': 0,
              'session_state': '8f558797-50e7-496d-bb45-3b5ac9fdcddb',
              'scope': 'profile email'}

        """
        url_path = f"/realms/{self.OIDC_REALM}/protocol/openid-connect/token"
        data = {
            "client_id": client_id,
            "grant_type": "password",
            "scope": "profile email",
            "username": username,
            "password": password,
        }
        return self.post(path=url_path, data=data).json()

    def get_user(self, username: str, token: str) -> dict:
        """Get the OIDC user representation dict.

        Args:
            username: username to query
            token: access_token string to validate

        Returns:
            User dict representation

            {'id': '37117992-a3de-43f7-b844-e6ee178e9965',
            'createdTimestamp': 1675981768951,
            'username': 'admin',
            'enabled': True,
            'totp': False,
            'emailVerified': False,
            'disableableCredentialTypes': [],
            'requiredActions': [],
            'notBefore': 0,
            'access': {'manageGroupMembership': True, 'view': True, 'mapRoles': True, 'impersonate': True, 'manage': True}
            ...
            }
        """
        response = self.get(
            f"admin/realms/{self.OIDC_REALM}/users",
            headers={"Authorization": f"Bearer {token}"},
            username=username,
        )
        if response.status_code == HTTPStatus.OK:
            return response.json()[0]
        return {}
