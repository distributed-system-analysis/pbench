"""OpenID Connect (OIDC) Client object definition."""

from configparser import NoOptionError, NoSectionError
from dataclasses import dataclass
from http import HTTPStatus
from typing import Dict, Optional, Union
from urllib.parse import urljoin

import jwt
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.structures import CaseInsensitiveDict

from pbench.server import JSON
from pbench.server.globals import server


class OpenIDClientError(Exception):
    def __init__(self, http_status: int, message: str = None):
        self.http_status = http_status
        self.message = message if message else HTTPStatus(http_status).phrase

    def __repr__(self) -> str:
        return f"OIDC error {self.http_status} : {str(self)}"

    def __str__(self) -> str:
        return self.message


class OpenIDTokenInvalid(Exception):
    pass


class Connection:
    """Helper connection class for use by an OpenIDClient instance."""

    def __init__(
        self,
        server_url: str,
        headers: Optional[Dict[str, str]] = None,
        verify: bool = True,
    ):
        self.server_url = server_url
        self.headers = CaseInsensitiveDict({} if headers is None else headers)
        self.verify = verify
        self._connection = requests.Session()

    def _method(
        self,
        method: str,
        path: str,
        data: Union[Dict, None],
        headers: Optional[Dict] = None,
        **kwargs,
    ) -> requests.Response:
        """Common frontend for the HTTP operations on OIDC client connection.

        Args:
            method : The API HTTP method
            path : Path for the request.
            data : Json data to send with the request in case of the POST
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
        try:
            response = self._connection.request(method, url, **kwargs)
        except requests.exceptions.ConnectionError as exc:
            raise OpenIDClientError(
                http_status=HTTPStatus.BAD_GATEWAY,
                message=(
                    f"Failure to connect to the OpenID client ({method} {url}"
                    f" {kwargs}): {exc}"
                ),
            )
        except requests.exceptions.Timeout as exc:
            raise OpenIDClientError(
                http_status=HTTPStatus.BAD_GATEWAY,
                message=(
                    f"Timeout talking to the OpenID client ({method} {url}"
                    f" {kwargs}): {exc}"
                ),
            )
        except Exception as exc:
            raise OpenIDClientError(
                http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
                message=(
                    "Unexpected exception talking to the OpenID client,"
                    f" ({method} {url} {kwargs}): {exc}"
                ),
            )
        else:
            if not response.ok:
                raise OpenIDClientError(
                    http_status=response.status_code,
                    message=f"Failed performing {method} {url} {kwargs}",
                )
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
        self, path: str, data: Dict, headers: Optional[Dict] = None, **kwargs
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


@dataclass
class InternalUser:
    """Internal user class for storing user related fields fetched
    from OIDC token decode.

    Note: Class attributes are duck-typed from the SQL User object,
    and they need to match with the respective sql entry!
    """

    id: str
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    roles: Optional[list[str]] = None

    def __str__(self) -> str:
        return f"User, id: {self.id}, username: {self.username}"

    def is_admin(self):
        return self.roles and ("ADMIN" in self.roles)

    @classmethod
    def create(cls, client_id: str, token_payload: dict) -> "InternalUser":
        """Helper method to return the Internal User object.

        Args:
            client_id : authorized client id string
            token_payload : Dict representation of decoded token

        Returns:
             InternalUser object
        """
        audiences = token_payload.get("resource_access", {})
        try:
            roles = audiences[client_id].get("roles", [])
        except KeyError:
            roles = []
        return cls(
            id=token_payload["sub"],
            username=token_payload.get("preferred_username"),
            email=token_payload.get("email"),
            first_name=token_payload.get("given_name"),
            last_name=token_payload.get("family_name"),
            roles=roles,
        )


class OpenIDClient:
    """OpenID Connect client object"""

    # Default token algorithm to use.
    _TOKEN_ALG = "RS256"

    class NotConfigured(Exception):
        """Indicate to the caller a OIDC server is not configured."""

        pass

    class ServerConnectionError(Exception):
        """Indicate to the caller an unexpected connection error occurred while
        attempting to connect to the OIDC server.
        """

        pass

    class ServerConnectionTimedOut(Exception):
        """Indicate to the caller we timed out attempting to connect to the
        OIDC server.
        """

        pass

    @staticmethod
    def wait_for_oidc_server() -> str:
        """Wait for the configured OIDC server to become available.

        Checks if the OIDC server is up and accepting the connections.  The
        connection check does the GET request on the OIDC server /health
        endpoint and the sample response returned by the /health endpoint looks
        like the following:

            {
                "status": "UP", # if the server is up
                "checks": []
            }

        Note: The OIDC server needs to be configured with health-enabled on.

        Raises:

            OpenIDClient.NotConfigured : when the given server configuration
                does not contain the required connection information.
            OpenIDClient.ServerConnectionError : when any unexpected errors are
                encountered trying to connect to the OIDC server.
            OpenIDClient.ServerConnectionTimeOut : when the connection attempt
                times out.
        """
        try:
            oidc_server = server.config.get("openid-connect", "server_url")
        except (NoOptionError, NoSectionError) as exc:
            raise OpenIDClient.NotConfigured() from exc

        server.logger.info("Waiting for OIDC server to become available.")

        session = requests.Session()
        # The connection check will retry multiple times unless successful, viz.,
        # [0.0s, 4.0s, 8.0s, 16.0s, ..., 120.0s]. urllib3 will sleep for:
        # {backoff factor} * (2 ^ ({number of total retries} - 1)) seconds between
        # the retries. However, the sleep will never be longer than backoff_max
        # which defaults to 120.0s More detailed documentation on Retry and
        # backoff_factor can be found at:
        # https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#module-urllib3.util.retry
        retry = Retry(
            total=8,
            backoff_factor=2,
            status_forcelist=tuple(int(x) for x in HTTPStatus if x != 200),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)

        # We will also need to retry the connection if the health status is not UP.
        connected = False
        for _ in range(5):
            try:
                response = session.get(f"{oidc_server}/health")
                response.raise_for_status()
            except Exception as exc:
                raise OpenIDClient.ServerConnectionError() from exc
            if response.json().get("status") == "UP":
                server.logger.debug("OIDC server connection verified")
                connected = True
                break
            server.logger.error(
                "OIDC client not running, OIDC server response: {!r}", response.json()
            )
            retry.sleep()

        if not connected:
            raise OpenIDClient.ServerConnectionTimedOut()

        return oidc_server

    @classmethod
    def construct_oidc_client(cls) -> "OpenIDClient":
        """Convenience class method to optionally construct and return an
        OpenIDClient.

        Raises:
            OpenIDClient.NotConfigured : when the openid-connect section is
            missing, or any of the required options are missing.
        """
        try:
            server_url = server.config.get("openid-connect", "server_url")
            client = server.config.get("openid-connect", "client")
            realm = server.config.get("openid-connect", "realm")
            secret = server.config.get("openid-connect", "secret")
        except (NoOptionError, NoSectionError) as exc:
            raise OpenIDClient.NotConfigured() from exc

        return cls(
            server_url=server_url,
            client_id=client,
            realm_name=realm,
            client_secret_key=secret,
            verify=False,
        )

    def __init__(
        self,
        server_url: str,
        client_id: str,
        realm_name: str,
        client_secret_key: str,
        verify: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize an OpenID Connect Client object.

        We also connect to the given OIDC server to establish the known end
        points, and fetch the public key.

        Sets the well-known configuration endpoints for the current OIDC
        client. This includes common useful endpoints for decoding tokens,
        getting user information etc.

        ref: https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderConfig

        Args:
            server_url : OpenID Connect server auth url
            client_id : client id
            realm_name : realm name
            client_secret_key : client secret key
            verify : True if require valid SSL
            headers : dict of custom header to pass to each HTML request
        """
        self.client_id = client_id
        self._client_secret_key = client_secret_key
        self._realm_name = realm_name

        self._connection = Connection(server_url, headers, verify)

        realm_public_key_uri = f"realms/{self._realm_name}"
        response_json = self._connection.get(realm_public_key_uri).json()
        public_key = response_json["public_key"]
        pem_public_key = "-----BEGIN PUBLIC KEY-----\n"
        while public_key:
            pk64 = public_key[:64]
            pem_public_key += f"{pk64}\n"
            public_key = public_key[64:]
        pem_public_key += "-----END PUBLIC KEY-----\n"
        self._pem_public_key = pem_public_key

        well_known_endpoint = ".well-known/openid-configuration"
        well_known_uri = f"realms/{self._realm_name}/{well_known_endpoint}"
        endpoints_json = self._connection.get(well_known_uri).json()

        try:
            self._userinfo_endpoint = endpoints_json["userinfo_endpoint"]
            self._tokeninfo_endpoint = endpoints_json["introspection_endpoint"]
        except KeyError as e:
            raise OpenIDClientError(
                HTTPStatus.BAD_GATEWAY,
                f"Missing endpoint {e!r} at {well_known_uri}; Endpoints found:"
                f" {endpoints_json}",
            )

    def __repr__(self):
        return (
            f"OpenIDClient(server_url={self._connection.server_url}, "
            f"client_id={self.client_id}, realm_name={self._realm_name}, "
            f"headers={self._connection.headers})"
        )

    def token_introspect_online(self, token: str) -> Optional[JSON]:
        """The introspection endpoint is used to retrieve the active state of a
        token.

        It can only be invoked by confidential clients.

        The introspected JWT token contains the claims specified in
        https://tools.ietf.org/html/rfc7662.

        Note: this is not supposed to be used in production, instead rely on
            offline token validation because of security concerns mentioned in
            https://www.rfc-editor.org/rfc/rfc7662.html#section-4.

        Args:
            token : token value to introspect

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
        if not self._tokeninfo_endpoint:
            return None

        payload = {
            "client_id": self.client_id,
            "client_secret": self._client_secret_key,
            "token": token,
        }
        token_payload = self._connection.post(
            self._tokeninfo_endpoint, data=payload
        ).json()

        audience = token_payload.get("aud")
        if not audience or self.client_id not in audience:
            # If our client is not an intended audience for the token,
            # we will not verify the token.
            token_payload = None

        return token_payload

    def token_introspect_offline(self, token: str) -> JSON:
        """Utility method to decode access/Id tokens using the public key
        provided by the identity provider.

        The introspected JWT token contains the claims specified in
        https://tools.ietf.org/html/rfc7662

        Please refer https://www.rfc-editor.org/rfc/rfc7662.html#section-4 for
        requirements on doing the token introspection offline.

        Args:
            token : token value to introspect

        Raises:
            OpenIDTokenInvalid : when token decode fails for expected reasons

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
        try:
            return jwt.decode(
                token,
                self._pem_public_key,
                algorithms=[self._TOKEN_ALG],
                audience=self.client_id,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_exp": True,
                },
            )
        except (
            jwt.ExpiredSignatureError,
            jwt.InvalidSignatureError,
            jwt.InvalidAudienceError,
        ) as exc:
            raise OpenIDTokenInvalid() from exc

    def get_userinfo(self, token: str = None) -> JSON:
        """The userinfo endpoint returns standard claims about the authenticated
        user, and is protected by a bearer token.

        FIXME - This method appears unused in the rest of the code.

        http://openid.net/specs/openid-connect-core-1_0.html#UserInfo

        Args:
            token : Valid token to extract the userinfo

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
        headers = {"Authorization": f"Bearer {token}"} if token else None
        return self._connection.get(self._userinfo_endpoint, headers=headers).json()
