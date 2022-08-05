from typing import Dict, List, Optional, Union
from urllib import parse

import requests
from requests.structures import CaseInsensitiveDict

# A type defined to conform to the semantic definition of a JSON structure
# with Python syntax.
JSONSTRING = str
JSONNUMBER = Union[int, float]
JSONVALUE = Union["JSONOBJECT", "JSONARRAY", JSONSTRING, JSONNUMBER, bool, None]
JSONARRAY = List[JSONVALUE]
JSONOBJECT = Dict[JSONSTRING, JSONVALUE]
JSON = JSONVALUE


class PbenchClientError(Exception):
    """
    Base class for exceptions reported by the Pbench Server client.
    """

    pass


class IncorrectParameterCount(PbenchClientError):
    def __init__(self, api: str, cnt: int, uri_params: Optional[JSONOBJECT]):
        self.api = api
        self.cnt = cnt
        self.uri_params = uri_params

    def __str__(self) -> str:
        return f"API template {self.api} requires {self.cnt} parameters ({self.uri_params})"


class PbenchServerClient:
    DEFAULT_SCHEME = "http"

    def __init__(self, host: str):
        """
        Create a Pbench Server client object.

        The connect method should be called to establish a connection and set
        up the endpoints map before using any other methods.

        Args:
            host: Pbench Server hostname
        """
        self.host: str = host
        url_parts = parse.urlsplit(host)
        if url_parts.scheme:
            self.scheme = url_parts.scheme
            url = self.host
        else:
            self.scheme = self.DEFAULT_SCHEME
            url = f"{self.scheme}://{self.host}"
        self.url = url
        self.username: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.session: Optional[requests.Session] = None
        self.endpoints: Optional[JSONOBJECT] = None

    def _headers(
        self, user_headers: Optional[Dict[str, str]] = None
    ) -> CaseInsensitiveDict:
        """
        Create an HTTP request headers dictionary.

        The connect method can set default HTTP headers which apply to all
        server calls. This method implicitly adds an authentication token
        if the client has logged in and also allows the caller to override
        that or any other default session header. (For example, to change the
        default "accept" datatype, or to force an invalid authentication token
        for testing.)

        Args:
            user_headers: Addition request headers

        Returns:
            Case-insensitive header dictionary
        """
        headers = CaseInsensitiveDict()
        if self.auth_token:
            headers["authorization"] = f"Bearer {self.auth_token}"
        if user_headers:
            headers.update(user_headers)
        return headers

    def _uri(self, api: str, uri_params: Optional[JSONOBJECT] = None) -> str:
        """
        Compute the Pbench Server URI for an operation. This uses the endpoints
        definition stored by connect. If parameters are given, then it will use
        the template "uri" object to find the named URI template and format it
        with the provided parameter values.

        Args:
            api: The name of the API
            uri_params: A dictionary of named parameter values for the template

        Returns:
            A fully specified URI
        """
        if not uri_params:
            return self.endpoints["api"][api]
        else:
            description = self.endpoints["uri"][api]
            template = description["template"]
            cnt = len(description["params"])
            if cnt != len(uri_params):
                raise IncorrectParameterCount(api, cnt, uri_params)
            return template.format(**uri_params)

    def get(
        self,
        api: str,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Issue a get HTTP operation through the cached session, constructing a
        URI from the "api" name and parameters, adding or overwriting HTTP
        request headers as specified.

        HTTP errors are raised by exception to ensure they're not overlooked.

        Args:
            api: The name of the Pbench Server API
            uri_params: A dictionary of named parameters to expand a URI template
            headers: A dictionary of header/value pairs
            kwargs: Additional `requests` parameters (e.g., params)

        Returns:
            An HTTP Response object
        """
        url = self._uri(api, uri_params)
        response = self.session.get(url, headers=self._headers(headers), **kwargs)
        response.raise_for_status()
        return response

    def head(
        self,
        api: str,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Issue a head HTTP operation through the cached session, constructing a
        URI from the "api" name and parameters, adding or overwriting HTTP
        request headers as specified. `head` is a GET that returns only status
        and headers, without a response payload.

        HTTP errors are raised by exception to ensure they're not overlooked.

        Args:
            api: The name of the Pbench Server API
            uri_params: A dictionary of named parameters to expand a URI template
            headers: A dictionary of header/value pairs
            kwargs: Additional `requests` parameters (e.g., params)

        Returns:
            An HTTP Response object
        """
        url = self._uri(api, uri_params)
        response = self.session.head(url, headers=self._headers(headers), **kwargs)
        response.raise_for_status()
        return response

    def put(
        self,
        api: str,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        json: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Issue a put HTTP operation through the cached session, constructing a
        URI from the "api" name and parameters, adding or overwriting HTTP
        request headers as specified, and optionally passing a JSON request
        payload.

        HTTP errors are raised by exception to ensure they're not overlooked.

        Args:
            api: The name of the Pbench Server API
            uri_params: A dictionary of named parameters to expand a URI template
            json: A JSON request payload as a Python dictionary
            headers: A dictionary of header/value pairs
            kwargs: Additional `requests` parameters (e.g., params)

        Returns:
            An HTTP Response object
        """
        url = self._uri(api, uri_params)
        response = self.session.put(
            url, json=json, headers=self._headers(headers), **kwargs
        )
        response.raise_for_status()
        return response

    def post(
        self,
        api: str,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        json: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Issue a post HTTP operation through the cached session, constructing a
        URI from the "api" name and parameters, adding or overwriting HTTP
        request headers as specified, and optionally passing a JSON request
        payload.

        HTTP errors are raised by exception to ensure they're not overlooked.

        Args:
            api: The name of the Pbench Server API
            uri_params: A dictionary of named parameters to expand a URI template
            json: A JSON request payload as a Python dictionary
            headers: A dictionary of header/value pairs
            kwargs: Additional `requests` parameters (e.g., params)

        Returns:
            An HTTP Response object
        """
        url = self._uri(api, uri_params)
        response = self.session.post(
            url, json=json, headers=self._headers(headers), **kwargs
        )
        response.raise_for_status()
        return response

    def delete(
        self,
        api: str,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Issue a delete HTTP operation through the cached session, constructing
        a URI from the "api" name and parameters, adding or overwriting HTTP
        request headers as specified.

        HTTP errors are raised by exception to ensure they're not overlooked.

        Args:
            api: The name of the Pbench Server API
            uri_params: A dictionary of named parameters to expand a URI template
            headers: A dictionary of header/value pairs
            kwargs: Additional `requests` parameters (e.g., params)

        Returns:
            An HTTP Response object
        """
        url = self._uri(api, uri_params)
        response = self.session.delete(url, headers=self._headers(headers), **kwargs)
        response.raise_for_status()
        return response

    def connect(self, headers: Optional[Dict[str, str]] = None) -> None:
        """
        Connect to the Pbench Server host using the endpoints API to be sure
        that it responds, and cache the endpoints response payload.

        This also allows the client to add default HTTP headers to the session
        which will be used for all operations unless overridden for specific
        operations.

        Args:
            headers: A dict of default HTTP headers
        """
        url = parse.urljoin(self.url, "api/v1/endpoints")
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)
        response = self.session.get(url)
        response.raise_for_status()
        self.endpoints = response.json()
        assert self.endpoints

    def login(self, user: str, password: str) -> None:
        """
        Login to a specified username with the password, and store the
        resulting authentication token.

        Args:
            user:       Account username
            password:   Account password
        """
        response = self.post("login", json={"username": user, "password": password})
        response.raise_for_status()
        json = response.json()
        self.username = json["username"]
        self.auth_token = json["auth_token"]

    def logout(self) -> None:
        """
        Logout the currently authenticated user and remove the authentication
        token.
        """
        self.post("logout")
        self.username = None
        self.auth_token = None
