import json
from typing import Dict, Optional, Union
from urllib.parse import urljoin

import requests
from requests.structures import CaseInsensitiveDict


class OIDCAdmin:
    def __init__(
        self,
        server_url: str,
        headers: Optional[Dict[str, str]] = None,
        verify: bool = False,
    ):
        self.server_url = server_url
        self.headers = CaseInsensitiveDict({} if headers is None else headers)
        self.verify = verify
        self._connection = requests.Session()

    def _method(
        self,
        method: str,
        path: str,
        data: Union[Dict, str, None],
        headers: Optional[Dict] = None,
        raise_error: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Common frontend for the HTTP operations on OIDC client connection.

        Args:
            method : The API HTTP method
            path : Path for the request.
            data : Json data to send with the request in case of the POST
            headers : Optional headers to send with request
            kwargs : Additional keyword args

        Returns:
            Response from the request.
        """
        final_headers = self.headers.copy()
        if headers is not None:
            final_headers.update(headers)
        url = urljoin(self.server_url, path)
        kwargs = dict(
            params=kwargs,
            data=data,
            headers=final_headers,
            verify=self.verify,
        )
        response = self._connection.request(method, url, **kwargs)
        if raise_error:
            response.raise_for_status()
        return response

    def get(
        self, path: str, headers: Optional[Dict] = None, **kwargs
    ) -> requests.Response:
        """GET wrapper to handle an authenticated GET operation on the Resource
        at a given path.

        Args:
            path : Path for the request
            headers : Additional headers to add to the request
            kwargs : Additional keyword args to be added as URL parameters

        Returns:
            Response from the request.
        """
        return self._method("GET", path, None, headers=headers, **kwargs)

    def post(
        self,
        path: str,
        data: Union[Dict, str],
        headers: Optional[Dict] = None,
        **kwargs,
    ) -> requests.Response:
        """POST wrapper to handle an authenticated POST operation on the
        Resource at a given path.

        Args:
            path : Path for the request
            data : JSON request body
            headers : Additional headers to add to the request
            kwargs : Additional keyword args to be added as URL parameters

        Returns:
            Response from the request.
        """
        return self._method("POST", path, data, headers=headers, **kwargs)

    def get_admin_token(self) -> requests.Response:
        url_path = "/realms/master/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "admin",
            "password": "admin",
        }
        return self.post(path=url_path, data=data)

    def get_client_secret(self, client_id: str) -> requests.Response:
        admin_token = self.get_admin_token().json().get("access_token")
        url_path = f"admin/realms/pbench-server/clients?clientId={client_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {admin_token}",
        }
        response = self.get(path=url_path, headers=headers)
        return response.json()[0]["secret"]

    def create_new_user(
        self,
        username: str,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
    ) -> requests.Response:
        admin_token = self.get_admin_token().json().get("access_token")
        url_path = "/admin/realms/pbench-server/users"
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

    def user_login(
        self, client_id: str, username: str, password: str, client_secret: str = None
    ) -> requests.Response:
        url_path = "/realms/pbench-server/protocol/openid-connect/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        client_secret = (
            client_secret
            if client_secret
            else self.get_client_secret(client_id=client_id)
        )
        data = {
            "client_id": client_id,
            "grant_type": "password",
            "client_secret": client_secret,
            "scope": "profile email",
            "username": username,
            "password": password,
        }
        response = self.post(path=url_path, data=data, headers=headers)
        return response
