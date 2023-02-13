from http import HTTPStatus
import json

import requests

from pbench.server.auth import Connection


class OIDCAdmin(Connection):
    OIDC_REALM = "pbench-server"
    OIDC_CLIENT = "pbench-dashboard"
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "123"

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
            "username": "admin",
            "password": "admin",
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
        """Creates a new user under the OIDC_REALM and assign OIDC_CLIENT_ROLE
        to the new user.

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
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}",
        }
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
        response = self.post(path=url_path, data=json.dumps(data), headers=headers)
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
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": client_id,
            "grant_type": "password",
            "scope": "profile email",
            "username": username,
            "password": password,
        }
        response = self.post(path=url_path, data=data, headers=headers)
        return response.json()

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
            f"admin/realms/{self.OIDC_REALM}/users?username={username}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            verify=False,
        )
        if response.status_code == HTTPStatus.OK:
            return response.json()[0]
        return {}
