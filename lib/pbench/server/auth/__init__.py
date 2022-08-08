import logging
from http import HTTPStatus
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin

import jwt
import requests
from flask_restful import abort
from jwt import PyJWKClient
from requests.structures import CaseInsensitiveDict

from pbench.server import JSON
from pbench.server.auth.exceptions import OidcError


class OpenIDClient:
    """
    OpenID client object.
    :param server_url: Keycloak server url
    :param client_id: client id
    :param realm_name: realm name
    :param client_secret_key: client secret key
    :param verify: True if want check connection SSL
    :param headers: dict of custom header to pass to each HTML request
    """

    AUTHORIZATION_ENDPOINT: str = ""
    TOKEN_ENDPOINT: str = ""
    USERINFO_ENDPOINT: str = ""
    REVOCATION_ENDPOINT: str = ""
    JWKS_URI: str = ""
    LOGOUT_ENDPOINT: str = ""

    def __init__(
        self,
        server_url: str,
        client_id: str,
        logger: logging.Logger,
        realm_name: str = None,
        client_secret_key: str = None,
        verify: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.server_url = server_url
        self.client_id = client_id
        self.client_secret_key = client_secret_key
        self.realm_name = realm_name
        self.logger = logger
        self.headers = headers if headers is not None else CaseInsensitiveDict()
        self.verify = verify
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
        del self.headers[key]

    def set_well_known_endpoints(self):
        """Sets the well-known configuration endpoints for the current oidc client.
        This includes common useful endpoints for decoding tokens, getting user
        information etc.
        """
        well_known_endpoint = "/.well-known/openid-configuration"
        if self.realm_name:
            well_known_uri = f"{self.server_url}{self.realm_name}{well_known_endpoint}"
        else:
            well_known_uri = f"{self.server_url}{well_known_endpoint}"
        endpoints_json = self._get(well_known_uri).json()
        try:
            OpenIDClient.AUTHORIZATION_ENDPOINT = endpoints_json[
                "authorization_endpoint"
            ]
            OpenIDClient.TOKEN_ENDPOINT = endpoints_json["token_endpoint"]
            OpenIDClient.USERINFO_ENDPOINT = endpoints_json["userinfo_endpoint"]
            OpenIDClient.REVOCATION_ENDPOINT = endpoints_json["revocation_endpoint"]
            OpenIDClient.JWKS_ENDPOINT = endpoints_json["jwks_uri"]
            if "end_session_endpoint" in endpoints_json:
                OpenIDClient.LOGOUT_ENDPOINT = endpoints_json["end_session_endpoint"]
        except KeyError as e:
            self.logger.exception("{}", str(e))
            raise

    def get_oidc_public_key(self, token):
        """
        Returns the Oidc client public key that can be used for decoding tokens offline.
        """
        jwks_client = PyJWKClient(self.JWKS_URI)
        pubkey = jwks_client.get_signing_key_from_jwt(token).key
        return pubkey

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
        what authentication flow is used. The token endpoint is also used to obtain new access tokens
        when they expire.
        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint
        Note: Some oidc clients only accept authorization_code as a grant_type for getting a token,
        getting token directly from these clients with username and password over an API call will result
        in Forbidden error.
        """
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

        return self._post(self.TOKEN_ENDPOINT, data=payload).json()

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
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "grant_type": grant_type,
            "scope": scope,
        }
        if extra:
            payload.update(extra)

        return self._post(self.TOKEN_ENDPOINT, data=payload).json()

    def user_refresh_token(self, refresh_token: str) -> JSON:
        """
        The token refresh endpoint is used to refresh the soon expiring access tokens.
        Note: it issues a new access token.
        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "grant_type": ["refresh_token"],
            "refresh_token": refresh_token,
        }
        return self._post(self.TOKEN_ENDPOINT, data=payload).json()

    def token_introspect_online(self, token: str, token_info_uri: str) -> JSON:
        """
        The introspection endpoint is used to retrieve the active state of a token.
        It can only be invoked by confidential clients.
        The introspected JWT token contains the claims specified in https://tools.ietf.org/html/rfc7662
        Note: this is not supposed to be used in production, instead rely on offline token validation
        :param token: token value to introspect
        :param token_info_uri: token introspection uri,
                this uri format may be different for different identity providers
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "token": token,
        }
        return self._post(token_info_uri, data=payload).json()

    def token_introspect_offline(
        self,
        token: str,
        key: str,
        audience: str = "account",
        algorithms: List[str] = ["RS256"],
        **kwargs,
    ) -> JSON:
        """
        Utility method to decode access/Id tokens using the public key provided by the identity provider
        The introspected JWT token contains the claims specified in https://tools.ietf.org/html/rfc7662
        :param token: token value to introspect
        :param key: client public key
        :param audience: jwt token audience/client, who this token was intended for
        :param algorithms: Algorithm with which this JWT token was encoded
        """
        return jwt.decode(
            token, key, algorithms=algorithms, audience=audience, **kwargs
        )

    def get_userinfo(self, token: str = None) -> JSON:
        """
        The userinfo endpoint returns standard claims about the authenticated user,
        and is protected by a bearer token.
        http://openid.net/specs/openid-connect-core-1_0.html#UserInfo
        """

        if token:
            self.add_header_param("Authorization", f"Bearer {token}")

        return self._get(self.USERINFO_ENDPOINT).json()

    def logout(self, refresh_token: str):
        """
        The logout endpoint logs out the authenticated user.
        :param refresh_token: Refresh token issued at the time of login
        """
        if self.LOGOUT_ENDPOINT:
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret_key,
                "refresh_token": refresh_token,
            }

            return self._post(self.LOGOUT_ENDPOINT, data=payload)
        else:
            self.logger.warning("logout attempt on third party token")
            abort(
                HTTPStatus.METHOD_NOT_ALLOWED,
                message="Logout operation is not allowed for the given token",
            )

    def revoke_access_token(self, access_token: str) -> HTTPStatus:
        """
        Revoke endpoint to revoke the current access token. It does not however, logs the refresh token out
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "token": access_token,
            "token_type_hint": "access_token",
        }

        return HTTPStatus(
            self._post(self.REVOCATION_ENDPOINT, data=payload).status_code
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
                verify=self.verify,
            )
        except Exception as exc:
            self.logger.exception("{}", str(exc))
            raise OidcError(
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
                verify=self.verify,
            )
        except Exception as exc:
            self.logger.exception("{}", str(exc))
            raise OidcError(
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
                verify=self.verify,
            )
        except Exception as exc:
            self.logger.exception("{}", str(exc))
            raise OidcError(
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
                verify=self.verify,
            )
        except Exception as exc:
            self.logger.exception("{}", str(exc))
            raise OidcError(
                HTTPStatus.INTERNAL_SERVER_ERROR, f"Can't connect to server {exc}"
            )
