"""OpenID Connect (OIDC) Client object definition."""

from configparser import NoOptionError, NoSectionError
from http import HTTPStatus
import logging
from typing import Any, Optional
from urllib.parse import urljoin

import jwt
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.structures import CaseInsensitiveDict

from pbench.server import JSON, PbenchServerConfig


class OpenIDClientError(Exception):
    def __init__(self, http_status: int, message: str = None):
        self.http_status = http_status
        self.message = message if message else HTTPStatus(http_status).phrase

    def __repr__(self) -> str:
        return f"OIDC error {self.http_status} : {str(self)}"

    def __str__(self) -> str:
        return self.message


class Connection:
    """Helper connection class for use by an OpenIDClient instance."""

    def __init__(
        self,
        server_url: str,
        headers: Optional[dict[str, str]] = None,
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
        data: Optional[Any] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """Common frontend for the HTTP operations on OIDC client connection.

        Args:
            method : The API HTTP method
            path : Path for the request.
            data : Form data to send with the request in case of the POST
            json : JSON data to send with the request in case of the POST
            kwargs : Additional keyword args

        Returns:
            Response from the request.
        """
        final_headers = self.headers.copy()
        if headers is not None:
            final_headers.update(headers)
        url = urljoin(self.server_url, path)
        request_dict = dict(
            params=kwargs,
            data=data,
            json=json,
            headers=final_headers,
            verify=self.verify,
        )
        try:
            response = self._connection.request(method, url, **request_dict)
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
        self, path: str, headers: Optional[dict[str, str]] = None, **kwargs
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
        return self._method("GET", path, headers=headers, **kwargs)

    def post(
        self,
        path: str,
        data: Optional[Any] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """POST wrapper to handle an authenticated POST operation on the
        Resource at a given path.

        Args:
            path : Path for the request
            data : Optional HTML form body to attach
            json : JSON request body
            headers : Additional headers to add to the request
            kwargs : Additional keyword args to be added as URL parameters

        Returns:
            Response from the request.
        """
        return self._method("POST", path, data, json, headers=headers, **kwargs)


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
    def wait_for_oidc_server(
        server_config: PbenchServerConfig, logger: logging.Logger
    ) -> str:
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

        Args:
            server_config : the Pbench Server configuration to use
            logger : the logger to use

        Raises:

            OpenIDClient.NotConfigured : when the given server configuration
                does not contain the required connection information.
            OpenIDClient.ServerConnectionError : when any unexpected errors are
                encountered trying to connect to the OIDC server.
            OpenIDClient.ServerConnectionTimeOut : when the connection attempt
                times out.
        """
        try:
            oidc_server = server_config.get("openid", "server_url")
            cert = server_config.get("openid", "cert_location")
        except (NoOptionError, NoSectionError) as exc:
            raise OpenIDClient.NotConfigured() from exc

        logger.info("Waiting for OIDC server to become available.")

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
        session.mount("https://", adapter)

        # We will also need to retry the connection if the health status is not UP.
        connected = False
        for _ in range(5):
            try:
                response = session.get(f"{oidc_server}/health", verify=cert)
                response.raise_for_status()
            except Exception as exc:
                raise OpenIDClient.ServerConnectionError() from exc
            if response.json().get("status") == "UP":
                logger.debug("OIDC server connection verified")
                connected = True
                break
            logger.error(
                "OIDC client not running, OIDC server response: {!r}", response.json()
            )
            retry.sleep()

        if not connected:
            raise OpenIDClient.ServerConnectionTimedOut()

        return oidc_server

    @classmethod
    def construct_oidc_client(cls, server_config: PbenchServerConfig) -> "OpenIDClient":
        """Convenience class method to optionally construct and return an
        OpenIDClient.

        Raises:
            OpenIDClient.NotConfigured : when the openid-connect section is
            missing, or any of the required options are missing.
        """
        try:
            server_url = server_config.get("openid", "server_url")
            client = server_config.get("openid", "client")
            realm = server_config.get("openid", "realm")
        except (NoOptionError, NoSectionError) as exc:
            raise OpenIDClient.NotConfigured() from exc

        oidc_client = cls(
            server_url=server_url,
            client_id=client,
            realm_name=realm,
            verify=False,
        )
        oidc_client.set_oidc_public_key()
        return oidc_client

    def __init__(
        self,
        server_url: str,
        client_id: str,
        realm_name: str,
        verify: bool = True,
        headers: Optional[dict[str, str]] = None,
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
            verify : True if require valid SSL
            headers : dict of custom header to pass to each HTML request
        """
        self.client_id = client_id
        self._realm_name = realm_name

        self._connection = Connection(server_url, headers, verify)

        self._pem_public_key = None

    def __repr__(self):
        return (
            f"OpenIDClient(server_url={self._connection.server_url}, "
            f"client_id={self.client_id}, realm_name={self._realm_name}, "
            f"headers={self._connection.headers})"
        )

    def set_oidc_public_key(self):
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

    def token_introspect(self, token: str) -> JSON:
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
        return jwt.decode(
            token,
            self._pem_public_key,
            algorithms=[self._TOKEN_ALG],
            audience=[self.client_id],
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True,
            },
        )
