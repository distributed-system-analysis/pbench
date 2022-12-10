from http import HTTPStatus
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin

import jwt
import requests
from requests.structures import CaseInsensitiveDict

from pbench.server import JSON


class OpenIDClientError(Exception):
    def __init__(self, http_status: int, message: str = None):
        self.http_status = http_status
        self.message = message if message else HTTPStatus(http_status).phrase

    def __repr__(self) -> str:
        return f"Oidc error {self.http_status} : {str(self)}"

    def __str__(self) -> str:
        return self.message


class OpenIDCAuthenticationError(OpenIDClientError):
    pass


class OpenIDClient:
    """
    OpenID Connect client object.
    """

    USERINFO_ENDPOINT: Optional[str] = None
    TOKENINFO_ENDPOINT: Optional[str] = None

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
        self.headers = CaseInsensitiveDict([] if headers is None else headers)
        self.verify = verify
        self.connection = requests.session()
        self.public_key = None

        # Warning: Note that the method we're calling now depends both on
        # self.realm_name being set plus any attribute dependencies of
        # self._get(). It is important to call set_well_known_endpoints after
        # setting all the required instance variables above.
        # TODO: Think about a better way to set well known endpoints
        #  https://github.com/distributed-system-analysis/pbench/issues/3102
        self.set_well_known_endpoints()

    def __repr__(self):
        return (
            f"OpenIDClient(server_url={self.server_url}, "
            f"client_id={self.client_id}, realm_name={self.realm_name}, "
            f"headers={self.headers})"
        )

    def add_header_param(self, key: str, value: str):
        """
        Add a single parameter inside the header.
        Args:
            key: Header parameters key.
            value: Value to be added for the key.
        """
        self.headers[key] = value

    def del_header_params(self, key: str):
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
        well_known_uri = (
            f"{self.server_url}/realms/{self.realm_name}{well_known_endpoint}"
        )
        endpoints_json = self._get(well_known_uri).json()
        try:
            OpenIDClient.USERINFO_ENDPOINT = endpoints_json.get("userinfo_endpoint")
            OpenIDClient.TOKENINFO_ENDPOINT = endpoints_json.get(
                "introspection_endpoint"
            )
        except KeyError as e:
            self.logger.exception(
                "Missing endpoint {!r} at {}; Endpoints found: {}",
                str(e),
                well_known_uri,
                endpoints_json,
            )
            raise

    def _get_oidc_public_key(self) -> str:
        """Returns the public key of the current OIDC client.

        Note: Caller of this method could receive any exceptions
        raised by self._get() in addition to the ones stated below.

        Returns:
            public key string

        Raises:
            KeyError: if public key not found in response payload
        """

        realm_public_key_uri = f"{self.server_url}/realms/{self.realm_name}"
        response_json = self._get(realm_public_key_uri).json()
        public_key = response_json["public_key"]
        return (
            "-----BEGIN PUBLIC KEY-----\n" + public_key + "\n-----END PUBLIC KEY-----"
        )

    def get_oidc_public_key(self):
        """
        Returns the OIDC client public key that can be used for decoding
        tokens offline.
        """
        if not self.public_key:
            self.public_key = self._get_oidc_public_key()
        return self.public_key

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
                "aud": <targeted_audience_id>,
                "email_verified": <boolean>,
                "expires_in": <number_of_seconds>,
                "access_type": "offline",
                "exp": <unix_timestamp>,
                "azp": <client_id>,
                "scope": <scope_string>, # "openid email profile"
                "email": <user_email>,
                "sub": <user_id>
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

        Please refer https://www.rfc-editor.org/rfc/rfc7662.html#section-4 for
        requirements on doing the token introspection offline.
        Args:
            token: token value to introspect
            key: client public key
            audience: jwt token audience/client, who this token was intended for
            algorithms: Algorithm with which this JWT token was encoded
        Returns:
            Extracted token information
            {
                "aud": <targeted_audience_id>,
                "email_verified": <boolean>,
                "expires_in": <number_of_seconds>,
                "access_type": "offline",
                "exp": <unix_timestamp>,
                "azp": <client_id>,
                "scope": <scope_string>, # "openid email profile"
                "email": <user_email>,
                "sub": <user_id>
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
                "sub": <user_id>,
                "picture": <URL>,
                "locale": <locale_name>,
                "email_verified": <boolean>,
                "given_name": <given_name>,
                "email": <email_address>,
                "hd": <domain_name>,
                "name": <full_name>
            }
        """

        if token:
            self.add_header_param("Authorization", f"Bearer {token}")

        return self._get(self.USERINFO_ENDPOINT).json()

    def _method(
        self, method: str, path: str, data: Dict, **kwargs
    ) -> requests.Response:
        """
        Common frontend for the HTTP operations on OIDC client.
        Args:
            method: The API HTTP method
            path: Path for the request.
            data: Json data to send with the request in case of the POST
            kwargs: Additional keyword args
        Returns:
            Response from the request.
        """

        try:
            response = self.connection.request(
                method,
                urljoin(self.server_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                verify=self.verify,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError:
            raise OpenIDCAuthenticationError(response.status_code)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            self.logger.exception("Could not connect to the OIDC client {!r}", self)
            raise OpenIDClientError(
                HTTPStatus.BAD_GATEWAY,
                f"Failure to connect to the OpenID client {e}",
            )
        except Exception as exc:
            self.logger.exception(
                "{} request failed for OIDC client {!r}", method, self
            )
            raise OpenIDClientError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failure to complete the {method} request from the OpenID client {exc}",
            )

    def _get(self, path: str, **kwargs) -> requests.Response:
        """
        GET wrapper to handle an authenticated GET operation on the Resource at
        a given path.
        Args:
            path: Path for the request.
            kwargs: Additional keyword args
        Returns:
            Response from the request.
        """
        return self._method("GET", path, None, **kwargs)

    def _post(self, path: str, data: Dict, **kwargs) -> requests.Response:
        """
        POST wrapper to handle an authenticated POST operation on the Resource at
        a given path
        Args:
            path: Path for the request.
            data: JSON request body
            kwargs: Additional keyword args
        Returns:
            Response from the request.
        """
        return self._method("POST", path, data, **kwargs)
