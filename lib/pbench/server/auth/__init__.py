from http import HTTPStatus
import logging
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin

from flask_restful import abort
import jwt
import requests
from requests.structures import CaseInsensitiveDict

from pbench.server import JSON
from pbench.server.auth.exceptions import OpenIDClientError, OpenIDCAuthenticationError


class OpenIDClient:
    """
    OpenID Connect client object.
    """

    AUTHORIZATION_ENDPOINT: Optional[str] = None
    TOKEN_ENDPOINT: Optional[str] = None
    USERINFO_ENDPOINT: Optional[str] = None
    REVOCATION_ENDPOINT: Optional[str] = None
    JWKS_URI: Optional[str] = None
    LOGOUT_ENDPOINT: Optional[str] = None

    def __init__(
        self,
        server_url: str,
        client_id: str,
        logger: logging.Logger,
        realm_name: str = "",
        client_secret_key: Optional[str] = None,
        verify: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Args:
            server_url: OpenID Connect server auth url
            client_id: client id
            realm_name: realm name
            client_secret_key: client secret key
            verify: True if require valid SSL
            headers: dict of custom header to pass to each HTML request
        """
        self.server_url = server_url
        self.client_id = client_id
        self.client_secret_key = client_secret_key
        self.realm_name = realm_name
        self.logger = logger
        self.headers = (
            CaseInsensitiveDict() if headers is None else CaseInsensitiveDict(headers)
        )
        self.verify = verify
        self.connection = requests.session()
        self.connection.hooks = {
            "response": lambda r, *args, **kwargs: r.raise_for_status()
        }
        self.set_well_known_endpoints()

    def __repr__(self):
        return (
            f"OpenIDClient(server_url={self.server_url}, "
            f"client_id={self.client_id}, realm_name={self.realm_name}, "
            f"headers={self.headers})"
        )

    def get_header_param(self, key: str) -> str:
        """
        Return a specific header parameter value.
        Args:
            key: header key
        Returns:
             Header parameters value.
        """
        return self.headers.get(key)

    def add_header_param(self, key: str, value: str):
        """
        Add a single parameter inside the header.
        Args:
            key: Header parameters key.
            value: Value to be added for the key.
        """
        self.headers[key] = value

    def del_param_headers(self, key: str):
        """
        Remove a specific header parameter.
        Args:
            Key to delete from the headers.
        """
        del self.headers[key]

    def set_well_known_endpoints(self):
        """
        Sets the well-known configuration endpoints for the current OIDC
        client. This includes common useful endpoints for decoding tokens,
        getting user information etc.
        ref: https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderConfig
        """
        well_known_endpoint = "/.well-known/openid-configuration"
        well_known_uri = f"{self.server_url}{self.realm_name}{well_known_endpoint}"
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
        except KeyError:
            self.logger.exception(
                f"Key Error while getting all the necessary URI endpoints from "
                f"{well_known_uri}; Endpoints json returned by the client: "
                f"{endpoints_json}"
            )
            raise

    def get_oidc_public_key(self, token: str):
        """
        Returns the OIDC client public key that can be used for decoding
        tokens offline.
        Args:
            token: Third party token to extract the signing key
        Returns:
            OIDC client public key
        """
        jwks_client = jwt.PyJWKClient(self.JWKS_URI)
        pubkey = jwks_client.get_signing_key_from_jwt(token).key
        return pubkey

    def get_user_token(
        self,
        username: str,
        password: str = None,
        grant_type: str = "password",
        scope: Union[str, List[str]] = "openid profile email",
        **extra,
    ) -> JSON:
        """
        The token endpoint is used to obtain tokens. Tokens can either be
        obtained by exchanging an authorization code or by supplying credentials
        directly depending on what authentication flow is used. The token
        endpoint is also used to obtain new access tokens when they expire.
        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint
        Note: Some OIDC clients only accept authorization_code as a grant_type
        for getting a token, getting a token directly from these clients with
        username and password over an API call will result in Forbidden error.
        Args:
            username: username that is registered under this OIDC client
            password: optional password field
            grant_type: "password"/"authorization_code" etc
            scope: user scope to that should be included in the token
        Returns:
            OIDC client access token payload
            e.g: json_response = {
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2l",
            "expires_in": 300,
            "refresh_expires_in": 1800,
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA",
            "token_type": "Bearer",
            "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwiPt_h5LI70",
            "not-before-policy": 0,
            "session_state": "a46aca36-78e3-4b2a-90b3-7bd46d5ff70d",
            "scope": "openid profile email",
            }
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
        The token endpoint is used to obtain client service token to do certain
        privilege stuff based on what roles this client service token has.
        Client service tokens do not have a session associated with them so
        they don't have a refresh token.
        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint
        Args:
            grant_type: "client_credential"
                        (most often client_credential is the correct grant
                        type to get the service token)
            scope: service scopes to that should be included in the token
        Returns:
            OIDC client access token payload
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
        The token refresh endpoint is used to refresh the soon expiring access
        tokens.
        Note: it issues a new access and refresh token.
        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint
        Args:
            refresh_token: refresh token str to get the new access token
        Returns:
            OIDC client access token payload
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret_key,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        return self._post(self.TOKEN_ENDPOINT, data=payload).json()

    def token_introspect_online(self, token: str, token_info_uri: str) -> JSON:
        """
        The introspection endpoint is used to retrieve the active state of a
        token.
        It can only be invoked by confidential clients.
        The introspected JWT token contains the claims specified in
        https://tools.ietf.org/html/rfc7662
        Note: this is not supposed to be used in production, instead rely on
              offline token validation because of security concerns mentioned in
              https://www.rfc-editor.org/rfc/rfc7662.html#section-4
        Args:
            token: token value to introspect
            token_info_uri: token introspection uri
        Returns:
            Extracted token information
            {
                "aud": "client_id",
                "email_verified": "true",
                "expires_in": "3572", # seconds
                "access_type": "offline",
                "exp": "1660087224",
                "azp": "client_id",
                "scope": "openid email profile",
                "email": "user@example.com",
                "sub": "106203657987367771589"
            }
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
        Utility method to decode access/Id tokens using the public key provided
        by the identity provider.
        The introspected JWT token contains the claims specified in
        https://tools.ietf.org/html/rfc7662
        Args:
            token: token value to introspect
            key: client public key
            audience: jwt token audience/client, who this token was intended for
            algorithms: Algorithm with which this JWT token was encoded
        Returns:
            Extracted token information
            {
                "aud": "client_id",
                "email_verified": "true",
                "expires_in": "3572", # seconds
                "access_type": "offline",
                "exp": "1660087224",
                "azp": "client_id",
                "scope": "openid email profile",
                "email": "user@example.com",
                "sub": "106203657987367771589"
            }
        """
        return jwt.decode(
            token, key, algorithms=algorithms, audience=audience, **kwargs
        )

    def get_userinfo(self, token: str = None) -> JSON:
        """
        The userinfo endpoint returns standard claims about the authenticated
        user, and is protected by a bearer token.
        http://openid.net/specs/openid-connect-core-1_0.html#UserInfo
        Args:
            token: Valid token to extract the userinfo
        Returns:
            Userinfo payload
            {
                "family_name": <surname>,
                "sub": "106203657987367771589",
                "picture": <URL>,
                "locale": "en",
                "email_verified": true,
                "given_name": <given-name>,
                "email": <email-address>,
                "hd": "redhat.com",
                "name": <full-name>
            }
        """

        if token:
            self.add_header_param("Authorization", f"Bearer {token}")

        return self._get(self.USERINFO_ENDPOINT).json()

    def logout(self, refresh_token: str) -> HTTPStatus:
        """
        The logout endpoint log out the authenticated user.
        Args:
            refresh_token: Refresh token issued at the time of login
        Returns:
            Https status code based on success or failure
        """
        if self.LOGOUT_ENDPOINT:
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret_key,
                "refresh_token": refresh_token,
            }

            return HTTPStatus(
                self._post(self.LOGOUT_ENDPOINT, data=payload).status_code
            )
        else:
            self.logger.warning("logout attempt on third party token")
            abort(
                HTTPStatus.METHOD_NOT_ALLOWED,
                message="Logout operation is not allowed for the given token",
            )

    def revoke_access_token(self, access_token: str) -> HTTPStatus:
        """
        Revoke endpoint to revoke the current access token. It does not,
        however, log the refresh token out.
        Args:
            access_token: token to revoke
        Returns:
            Https status code based on success or failure
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
        Args:
            path: Path for the request.
            kwargs: Params dict to send with GET request
        Returns:
            Response from the request.
        """

        try:
            response = self.connection.get(
                urljoin(self.server_url, path),
                params=kwargs,
                headers=self.headers,
                verify=self.verify,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if response.status_code == HTTPStatus.FORBIDDEN:
                raise OpenIDCAuthenticationError(
                    HTTPStatus.FORBIDDEN, f"Forbidden to perform the operation {e}"
                )
            elif response.status_code == HTTPStatus.UNAUTHORIZED:
                raise OpenIDCAuthenticationError(
                    HTTPStatus.UNAUTHORIZED,
                    f"Unauthorized to perform the operation {e}",
                )
        except requests.exceptions.ConnectionError as e:
            self.logger.exception(
                "GET request resulted in connection error {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to connect to the OpenID client {e}",
            )
        except requests.exceptions.Timeout as e:
            self.logger.exception(
                "GET request timeout error {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to connect to the OpenID client {e}",
            )

        except Exception as exc:
            self.logger.exception(
                "GET request failed for OIDC client {}", self.__repr__()
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to complete the GET request from the OpenID client {exc}",
            )

    def _post(self, path: str, data: Dict, **kwargs) -> requests.Response:
        """Submit post request to the path.
        Args:
            path: Path for the request.
            kwargs: Params dict to send with GET request
        Returns:
            Response from the request.
        """
        try:
            response = self.connection.post(
                urljoin(self.server_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                verify=self.verify,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if response.status_code == HTTPStatus.FORBIDDEN:
                raise OpenIDCAuthenticationError(
                    HTTPStatus.FORBIDDEN, f"Forbidden to perform the operation {e}"
                )
            elif response.status_code == HTTPStatus.UNAUTHORIZED:
                raise OpenIDCAuthenticationError(
                    HTTPStatus.UNAUTHORIZED,
                    f"Unauthorized to perform the operation {e}",
                )
        except requests.exceptions.ConnectionError as e:
            self.logger.exception(
                "POST request resulted in connection error {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to connect to the OpenID client {e}",
            )
        except requests.exceptions.Timeout as e:
            self.logger.exception(
                "POST request timeout error {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to connect to the OpenID client {e}",
            )

        except Exception as exc:
            self.logger.exception(
                "POST request failed for OIDC client {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to complete the POST request from the OpenID client {exc}",
            )

    def _put(self, path: str, data: Dict, **kwargs) -> requests.Response:
        """Submit put request to the path.
        Args:
            path: Path for the request.
            kwargs: Params dict to send with GET request
        Returns:
            Response from the request.
        """
        try:
            response = self.connection.put(
                urljoin(self.server_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                verify=self.verify,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if response.status_code == HTTPStatus.FORBIDDEN:
                raise OpenIDCAuthenticationError(
                    HTTPStatus.FORBIDDEN, f"Forbidden to perform the operation {e}"
                )
            elif response.status_code == HTTPStatus.UNAUTHORIZED:
                raise OpenIDCAuthenticationError(
                    HTTPStatus.UNAUTHORIZED,
                    f"Unauthorized to perform the operation {e}",
                )
        except requests.exceptions.ConnectionError as e:
            self.logger.exception(
                "PUT request resulted in connection error {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to connect to the OpenID client {e}",
            )
        except requests.exceptions.Timeout as e:
            self.logger.exception(
                "PUT request timeout error {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to connect to the OpenID client {e}",
            )

        except Exception as exc:
            self.logger.exception(
                "PUT request failed for OIDC client {}", self.__repr__()
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to complete the PUT request from the OpenID client {exc}",
            )

    def _delete(self, path: str, data: Dict = {}, **kwargs) -> requests.Response:
        """Submit delete request to the path.
        Args:
            path: Path for the request.
            kwargs: Params dict to send with GET request
        Returns:
            Response from the request.
        """
        try:
            response = self.connection.delete(
                urljoin(self.server_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                verify=self.verify,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if response.status_code == HTTPStatus.FORBIDDEN:
                raise OpenIDCAuthenticationError(
                    HTTPStatus.FORBIDDEN, f"Forbidden to perform the operation {e}"
                )
            elif response.status_code == HTTPStatus.UNAUTHORIZED:
                raise OpenIDCAuthenticationError(
                    HTTPStatus.UNAUTHORIZED,
                    f"Unauthorized to perform the operation {e}",
                )
        except requests.exceptions.ConnectionError as e:
            self.logger.exception(
                "DELETE request resulted in connection error {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to connect to the OpenID client {e}",
            )
        except requests.exceptions.Timeout as e:
            self.logger.exception(
                "DELETE request timeout error {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"OpenID client connection timed out {e}",
            )
        except Exception as exc:
            self.logger.exception(
                "DELETE request failed for OIDC client {}",
                self.__repr__(),
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to complete the DELETE request from the OpenID client {exc}",
            )
