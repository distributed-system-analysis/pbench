from http import HTTPStatus
from typing import Dict, List, Union
from urllib.parse import urljoin

import jwt
import requests

from pbench.server import JSON
from pbench.server.auth.auth_provider_urls import (
    URL_INTROSPECT,
    URL_LOGOUT,
    URL_REALM,
    URL_TOKEN,
    URL_USERINFO,
    URL_WELL_KNOWN,
)
from pbench.server.auth.exceptions import KeycloakConnectionError


class KeycloakOpenID:
    """
    Keycloak OpenID client.
    :param server_url: Keycloak server url
    :param client_id: client id
    :param realm_name: realm name
    :param client_secret_key: client secret key
    :param verify: True if want check connection SSL
    :param headers: dict of custom header to pass to each HTML request
    """

    def __init__(
        self,
        server_url: str,
        realm_name: str,
        client_id: str,
        logger,
        client_secret_key: str = None,
        verify: bool = True,
        headers: Dict = None,
        timeout: int = 60,
    ):
        self.server_url = server_url
        self.client_id = client_id
        self.client_secret_key = client_secret_key
        self.realm_name = realm_name
        self.logger = logger
        self.headers = headers if headers is not None else dict()
        self.verify = verify
        self.timeout = timeout
        self.connection = requests.session()

    def get_header_param(self, key: str) -> str:
        """
        Return a specific header parameter value.
        :param key: Header parameters key.
        """
        return self.headers.get(key)

    def add_header_param(self, key: str, value: str):
        """Add a single parameter inside the header.
        :param key: Header parameters key.
        :param value: Value to be added.
        """
        self.headers[key] = value

    def del_param_headers(self, key: str):
        """Remove a specific header parameter.
        :param key: Key of the header parameters.
        """
        self.headers.pop(key, None)

    def get_well_known(self) -> JSON:
        """Returns the well-known configuration endpoints as a JSON.
        It lists endpoints and other configuration options relevant to
        the OpenID implementation in Keycloak.
        """
        params_path = {"realm-name": self.realm_name}
        return self._get(URL_WELL_KNOWN.format(**params_path)).json()

    def get_realm_public_key(self):
        """
        The public key is exposed by the realm page directly.
        """
        params_path = {"realm-name": self.realm_name}
        return self._get(URL_REALM.format(**params_path)).json()

    def get_user_token(
        self,
        username: str,
        password: str,
        grant_type: str = "password",
        scope: Union[str, List[str]] = "openid profile email",
        **extra,
    ) -> JSON:
        """
        The token endpoint is used to obtain tokens. Tokens can either be obtained by
        exchanging an authorization code or by supplying credentials directly depending on
        what flow is used. The token endpoint is also used to obtain new access tokens
        when they expire.
        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint
        """
        params_path = {"realm-name": self.realm_name}
        payload = {
            "username": username,
            "password": password,
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "grant_type": grant_type,
            "scope": scope,
        }
        if extra:
            payload.update(extra)

        return self._post(URL_TOKEN.format(**params_path), data=payload).json()

    def get_client_service_token(
        self,
        grant_type: str = "client_credentials",
        scope: Union[str, List[str]] = "openid profile email",
        **extra,
    ) -> JSON:
        """
        The token endpoint is used to obtain client service token to do certain privilege stuff
        based on what roles this client service token has. Client service tokens do not have a
        session associated with them so they dont have a refresh token.
        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint
        :param grant_type:
        :param scope:
        :return:
        """
        params_path = {"realm-name": self.realm_name}
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "grant_type": grant_type,
            "scope": scope,
        }
        if extra:
            payload.update(extra)

        return self._post(URL_TOKEN.format(**params_path), data=payload).json()

    def user_refresh_token(self, refresh_token: str) -> JSON:
        """
        The token refresh endpoint is used to refresh the soon expiring access tokens.
        Note: it issues a new access token.
        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint
        """
        params_path = {"realm-name": self.realm_name}
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "grant_type": ["refresh_token"],
            "refresh_token": refresh_token,
        }
        return self._post(URL_TOKEN.format(**params_path), data=payload).json()

    def token_introspect_online(self, token: str) -> JSON:
        """
        The introspection endpoint is used to retrieve the active state of a token.
        It can only be invoked by confidential clients.
        The introspected JWT token contains the claims specified in https://tools.ietf.org/html/rfc7662
        :param token: token value to introspect
        """
        params_path = {"realm-name": self.realm_name}

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "token": token,
        }

        return self._post(URL_INTROSPECT.format(**params_path), data=payload).json()

    def token_introspect_offline(
        self, token: str, key: str, audience="account", algorithms=["RS256"], **kwargs
    ):
        """
        The introspection endpoint is used to retrieve the active state of a token.
        It can only be invoked by confidential clients.
        The introspected JWT token contains the claims specified in https://tools.ietf.org/html/rfc7662
        :param token: token value to introspect
        :param key: client public key
        :param audience: jwt token audience/client
        :param algorithms: Algorithm with which this JWT token was encoded
        """
        return jwt.decode(
            token, key, algorithms=algorithms, audience=audience, **kwargs
        )

    def get_userinfo(self, token: str) -> JSON:
        """
        The userinfo endpoint returns standard claims about the authenticated user,
        and is protected by a bearer token.
        http://openid.net/specs/openid-connect-core-1_0.html#UserInfo
        """

        self.add_header_param("Authorization", f"Bearer {token}")
        params_path = {"realm-name": self.realm_name}

        return self._get(URL_USERINFO.format(**params_path)).json()

    def logout(self, refresh_token: str) -> HTTPStatus:
        """
        The logout endpoint logs out the authenticated user.
        :param refresh_token: Refresh token issued at the time of login
        """
        params_path = {"realm-name": self.realm_name}
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "refresh_token": refresh_token,
        }

        return HTTPStatus(
            self._post(URL_LOGOUT.format(**params_path), data=payload).status_code
        )

    def revoke_access_token(self, access_token: str) -> HTTPStatus:
        """
        Revoke endpoint to revoke the current access token. It does not however, logs the refresh token out
        """
        params_path = {"realm-name": self.realm_name}
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "token": access_token,
            "token_type_hint": "access_token",
        }

        return HTTPStatus(
            self._post(URL_LOGOUT.format(**params_path), data=payload).status_code
        )

    def _get(self, path: str, **kwargs) -> requests.Response:
        """Submit get request to the path.
        :param path: Path for the request.
        :returns: Response from the request.
        """

        try:
            return self.connection.get(
                urljoin(self.server_url, path),
                params=kwargs,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify,
            )
        except Exception as exc:
            self.logger.exception("{}", str(exc))
            raise KeycloakConnectionError(
                HTTPStatus.INTERNAL_SERVER_ERROR, f"Can't connect to server {exc}"
            )

    def _post(self, path: str, data: Dict, **kwargs) -> requests.Response:
        """Submit post request to the path.
        :param path: Path for the request.
        :param data: Payload for the request.
        """
        try:
            return self.connection.post(
                urljoin(self.server_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify,
            )
        except Exception as exc:
            self.logger.exception("{}", str(exc))
            raise KeycloakConnectionError(
                HTTPStatus.INTERNAL_SERVER_ERROR, f"Can't connect to server {exc}"
            )

    def _put(self, path: str, data: Dict, **kwargs) -> requests.Response:
        """Submit put request to the path.
        :param path: Path for the request.
        :param data: Payload for the request.
        """
        try:
            return self.connection.put(
                urljoin(self.server_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify,
            )
        except Exception as exc:
            self.logger.exception("{}", str(exc))
            raise KeycloakConnectionError(
                HTTPStatus.INTERNAL_SERVER_ERROR, f"Can't connect to server {exc}"
            )

    def _delete(self, path: str, data: Dict = {}, **kwargs) -> requests.Response:
        """Submit delete request to the path.
        :param path: Path for the request.
        :param data: Payload for the request.
        """
        try:
            return self.connection.delete(
                urljoin(self.server_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify,
            )
        except Exception as exc:
            self.logger.exception("{}", str(exc))
            raise KeycloakConnectionError(
                HTTPStatus.INTERNAL_SERVER_ERROR, f"Can't connect to server {exc}"
            )
