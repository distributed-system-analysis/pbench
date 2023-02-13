from configparser import ConfigParser
from enum import Enum
from pathlib import Path
import tarfile
from typing import Any, Iterator, Optional
from urllib import parse

import requests
from requests.structures import CaseInsensitiveDict

from pbench.client.oidc_admin import OIDCAdmin
from pbench.client.types import Dataset, JSONOBJECT


class PbenchClientError(Exception):
    """Base class for exceptions reported by the Pbench Server client."""

    pass


class IncorrectParameterCount(PbenchClientError):
    """This exception is raised when a URI template is used and the provided
    parameter count doesn't match the template's expected count.
    """

    def __init__(self, api: str, cnt: int, uri_params: Optional[JSONOBJECT]):
        self.api = api
        self.cnt = cnt
        self.uri_params = uri_params

    def __str__(self) -> str:
        return f"API template {self.api} requires {self.cnt} parameters ({self.uri_params})"


class API(Enum):
    """Define the supported Pbench Server V1 API endpoints.

    Using an ENUM instead of string values allows IDE syntax checking and
    name completion.
    """

    DATASETS_CONTENTS = "datasets_contents"
    DATASETS_DATERANGE = "datasets_daterange"
    DATASETS_DELETE = "datasets_delete"
    DATASETS_DETAIL = "datasets_detail"
    DATASETS_INVENTORY = "datasets_inventory"
    DATASETS_LIST = "datasets_list"
    DATASETS_MAPPINGS = "datasets_mappings"
    DATASETS_METADATA = "datasets_metadata"
    DATASETS_NAMESPACE = "datasets_namespace"
    DATASETS_UPDATE = "datasets_update"
    DATASETS_SEARCH = "datasets_search"
    DATASETS_VALUES = "datasets_values"
    ENDPOINTS = "endpoints"
    SERVER_AUDIT = "server_audit"
    SERVER_CONFIGURATION = "server_configuration"
    UPLOAD = "upload"
    USER = "user"


class PbenchServerClient:
    DEFAULT_SCHEME = "http"
    DEFAULT_PAGE_SIZE = 100

    def __init__(self, host: str):
        """Create a Pbench Server client object.

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
        self.oidc_admin: Optional[OIDCAdmin] = None

    def _headers(
        self, user_headers: Optional[dict[str, str]] = None
    ) -> CaseInsensitiveDict:
        """Create an HTTP request headers dictionary.

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

    def _uri(self, api: API, uri_params: Optional[JSONOBJECT] = None) -> str:
        """Compute the Pbench Server URI for an operation. This uses the
        endpoints definition stored by connect. If parameters are given, then
        it will use the template "uri" object to find the named URI template
        and format it with the provided parameter values.

        Args:
            api: The API enum value
            uri_params: A dictionary of named parameter values for the template

        Returns:
            A fully specified URI
        """
        if not uri_params:
            return self.endpoints["api"][api.value]
        else:
            description = self.endpoints["uri"][api.value]
            template = description["template"]
            cnt = len(description["params"])
            if cnt != len(uri_params):
                raise IncorrectParameterCount(api, cnt, uri_params)
            return template.format(**uri_params)

    def get(
        self,
        api: Optional[API] = None,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        headers: Optional[dict[str, str]] = None,
        uri: Optional[str] = None,
        raise_error: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Issue a get HTTP operation through the cached session, constructing
        a URI from the "api" name and parameters, adding or overwriting HTTP
        request headers as specified.

        A "raw" unprocessed URI can be used by specifying the optional "uri"
        parameter, instead of "api" and "uri_params".

        HTTP errors are raised by exception to ensure they're not overlooked.

        Args:
            api: The Pbench Server API
            uri_params: A dictionary of named parameters to expand a URI template
            headers: A dictionary of header/value pairs
            uri: Specify a full URI instead of api and uri_params
            kwargs: Additional `requests` parameters (e.g., params)

        Returns:
            An HTTP Response object
        """
        url = uri if uri else self._uri(api, uri_params)
        response = self.session.get(url, headers=self._headers(headers), **kwargs)
        if raise_error:
            response.raise_for_status()
        return response

    def head(
        self,
        api: API,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        headers: Optional[dict[str, str]] = None,
        raise_error: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Issue a head HTTP operation through the cached session, constructing
        a URI from the "api" name and parameters, adding or overwriting HTTP
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
        if raise_error:
            response.raise_for_status()
        return response

    def put(
        self,
        api: API,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        raise_error: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Issue a put HTTP operation through the cached session, constructing
        a URI from the "api" name and parameters, adding or overwriting HTTP
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
        if raise_error:
            response.raise_for_status()
        return response

    def post(
        self,
        api: API,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        raise_error: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Issue a post HTTP operation through the cached session, constructing
        a URI from the "api" name and parameters, adding or overwriting HTTP
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
        if raise_error:
            response.raise_for_status()
        return response

    def delete(
        self,
        api: API,
        uri_params: Optional[JSONOBJECT] = None,
        *,
        headers: Optional[dict[str, str]] = None,
        raise_error: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Issue a delete HTTP operation through the cached session,
        constructing a URI from the "api" name and parameters, adding or
        overwriting HTTP request headers as specified.

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
        if raise_error:
            response.raise_for_status()
        return response

    def connect(self, headers: Optional[dict[str, str]] = None) -> None:
        """Performs some pre-requisite actions to make server client usable.

            1. Connect to the Pbench Server host using the endpoints API to be
            sure that it responds, and cache the endpoints response payload.

            2. Create an OIDCAdmin object that a server client can use to
            perform privileged actions on an OIDC server.

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

        # Create an OIDCAdmin object and confirm the connection was successful
        self.oidc_admin = OIDCAdmin(server_url=self.endpoints["openid"]["server"])

    def login(self, user: str, password: str):
        """Log into the OIDC server using the specified username and password,
        and store the resulting authentication token.

        Args:
            user:       Account username
            password:   Account password
        """
        response = self.oidc_admin.user_login(
            client_id=self.endpoints["openid"]["client"],
            username=user,
            password=password,
        )
        self.username = user
        self.auth_token = response["access_token"]

    def upload(self, tarball: Path, **kwargs) -> requests.Response:
        """Upload a tarball to the server.

        This requires that the "tarball" path have a companion {tarball}.md5
        file containing the MD5. It also requires that a user session be logged
        in on the PbenchServerClient.

        Args:
            tarball: path to a tarball file with a companion MD5 file
            kwargs: Use to override automatically generated headers
                md5: override companion MD5 value
                controller: override metadata.log controller
                filename: override the actual filename to provoke an error

        Raises:
            FileNotFound: The file or the companion MD5 file is missing
            HttpError: An HTTP or PUT API error occurs

        Returns:
            The PUT response object
        """
        query_parameters = {}

        md5 = kwargs.get("md5", Dataset.md5(tarball))
        access = kwargs.get("access", "private")
        if access == "public":
            query_parameters["access"] = access
        if "controller" in kwargs:
            controller = kwargs["controller"]
        else:
            with tarfile.open(tarball) as t:
                metafile = (
                    t.extractfile(f"{Dataset.stem(tarball)}/metadata.log")
                    .read()
                    .decode()
                )
            metadata = ConfigParser(interpolation=None)
            metadata.read_string(metafile)
            controller = metadata.get("run", "controller", fallback=None)

        headers = {
            "Content-MD5": md5,
            "controller": controller,
            "content-type": "application/octet-stream",
        }

        with tarball.open("rb") as f:
            return self.put(
                api=API.UPLOAD,
                uri_params={"filename": kwargs.get("filename", tarball.name)},
                headers=headers,
                params=query_parameters,
                data=f,
                raise_error=False,
            )

    def get_list(self, **kwargs) -> Iterator[Dataset]:
        """Return a list of datasets matching the specific search criteria and
        with the requested metadata items.

        This is a generator, which will page through all selected datasets in a
        series of paginated GET calls. If the "limit" keyword isn't specified,
        the default is PbenchServerClient.DEFAULT_PAGE_SIZE.

        Normally it makes no sense to specify "offset": the default is to page
        through all matches. However, if "offset" is specified, then a single
        call is made returning "limit" matches (or DEFAULT_PAGE_SIZE if not
        specified) at the specified offset in the list of matches. (As if a
        direct call to the raw GET API had been made.)

        Args:
            kwargs: query criteria
                metadata: list of requested metadata paths
                name:   name substring
                owner:  username of dataset owner
                access: dataset access setting
                start:  earliest creation date
                end:    latest creation date
                limit:  page size to override default

        Returns:
            A list of Dataset objects
        """
        args = kwargs.copy()
        if "limit" not in args:
            args["limit"] = self.DEFAULT_PAGE_SIZE
        json = self.get(api=API.DATASETS_LIST, params=args).json()
        while True:
            for d in json["results"]:
                yield Dataset(d)
            next_url = json.get("next_url")
            if "offset" in args or not next_url:
                break
            json = self.get(uri=next_url).json()

    def get_user(self, username: str, add_auth_header: bool = True) -> JSONOBJECT:
        """ """
        if add_auth_header:
            return self.get(
                api=API.USER, uri_params={"target_username": username}
            ).json()
        response = self.session.get(self._uri(API.USER, {"target_username": username}))
        response.raise_for_status()
        return response.json()

    def get_metadata(self, dataset_id: str, metadata: list[str]) -> JSONOBJECT:
        """Return requested metadata for a specified dataset.

        Args:
            dataset_id: the resource ID of the targeted dataset
            metadata: a list of metadata keys to return

        Returns:
            A JSON document containing the requested key values
        """
        return self.get(
            api=API.DATASETS_METADATA,
            uri_params={"dataset": dataset_id},
            params={"metadata": metadata},
        ).json()

    def set_metadata(self, dataset_id: str, metadata: JSONOBJECT) -> JSONOBJECT:
        """Set the requested metadata for a specified dataset.

        Args:
            dataset_id: the resource ID of the targeted dataset
            metadata: a JSON object with a value for each key

        Returns:
            A JSON document containing the new key values
        """
        return self.put(
            api=API.DATASETS_METADATA, uri_params={"dataset": dataset_id}, json=metadata
        ).json()
