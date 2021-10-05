import json
from datetime import datetime
from enum import Enum
from http import HTTPStatus
from json.decoder import JSONDecodeError
from logging import Logger
from typing import Any, AnyStr, Callable, Dict, List, Union

from dateutil import parser as date_parser
from flask import request
from flask.wrappers import Request, Response
from flask_restful import Resource, abort

from pbench.server import PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    MetadataBadKey,
    MetadataNotFound,
)
from pbench.server.database.models.users import User

# A type defined to conform to the semantic definition of a JSON structure
# with Python syntax.
JSONSTRING = str
JSONNUMBER = Union[int, float]
JSONVALUE = Union["JSONOBJECT", "JSONARRAY", JSONSTRING, JSONNUMBER, bool, None]
JSONARRAY = List[JSONVALUE]
JSONOBJECT = Dict[JSONSTRING, JSONVALUE]
JSON = JSONVALUE


class UnauthorizedAccess(Exception):
    """
    The user is not authorized for the requested operation on the specified
    resource.
    """

    def __init__(
        self,
        user: str,
        operation: "API_OPERATION",
        owner: str,
        access: str,
        status: int = HTTPStatus.FORBIDDEN,
    ):
        self.user = user
        self.operation = operation
        self.owner = owner
        self.access = access
        self.status = status

    def __str__(self) -> str:
        return f"{'User ' + self.user.username if self.user else 'Unauthenticated client'} is not authorized to {self.operation.name} a resource owned by {self.owner} with {self.access} access"


class SchemaError(TypeError):
    """
    Generic base class for errors in processing a JSON schema.
    """

    def __init__(self, status: int = HTTPStatus.BAD_REQUEST):
        self.http_status = status

    def __str__(self) -> str:
        return "Generic schema validation error"


class UnverifiedUser(SchemaError):
    """
    Attempt by an unauthenticated user to reference a username in a query. An
    unauthenticated client does not have the right to look up any username.

    HTTPStatus.UNAUTHORIZED tells the client that the operation might succeed
    if the request is retried with authentication. (A UI might redirect to a
    login page.)
    """

    def __init__(self, username: str):
        super().__init__(status=HTTPStatus.UNAUTHORIZED)
        self.username = username

    def __str__(self):
        return f"Caller is unable to verify username {self.username}"


class InvalidRequestPayload(SchemaError):
    """
    A required client JSON input document is missing.
    """

    def __str__(self) -> str:
        return "Invalid request payload"


class UnsupportedAccessMode(SchemaError):
    """
    Unsupported values for user or access, or an unsupported combination of
    both.
    """

    def __init__(self, user: str, access: str):
        super().__init__()
        self.user = user
        self.access = access

    def __str__(self) -> str:
        return f"Unsupported mode {self.user}:{self.access}"


class MissingParameters(SchemaError):
    """
    One or more required JSON keys are missing, or the values are unexpectedly
    empty.
    """

    def __init__(self, keys: List[AnyStr]):
        super().__init__()
        self.keys = sorted(keys)

    def __str__(self):
        return f"Missing required parameters: {','.join(self.keys)}"


class ConversionError(SchemaError):
    """
    Used to report an invalid parameter type
    """

    def __init__(self, value: Any, expected_type: str):
        """
        Construct a ConversionError exception

        Args:
            value: The value we tried to convert
            expected_type: The expected type
        """
        super().__init__()
        self.value = value
        self.expected_type = expected_type

    def __str__(self):
        return f"Value {self.value!r} ({type(self.value).__name__}) cannot be parsed as a {self.expected_type}"


class KeywordError(SchemaError):
    """
    Used to report an unrecognized keyword value.
    """

    def __init__(
        self,
        parameter: "Parameter",
        expected_type: str,
        unrecognized: List[str],
        *,
        keywords: List[str] = [],
    ):
        """
        Construct a KeywordError exception

        Args:
            parameter: The Parameter defining the keywords
            expected_type: The expected type ("keyword", "JSON")
            unrecognized: The unrecognized keywords
            keywords: If specified, overrides default keywords from parameter
        """
        super().__init__()
        self.parameter = parameter
        self.expected_type = expected_type
        self.unrecognized = sorted(unrecognized)
        self.keywords = sorted(keywords if keywords else parameter.keywords)

    def __str__(self):
        return f"Unrecognized {self.expected_type} {self.unrecognized!r} given for parameter {self.parameter.name}; allowed keywords are {self.keywords!r}"


class ListElementError(SchemaError):
    """
    Used to report an unrecognized list element value.
    """

    def __init__(self, parameter: "Parameter", bad: List[str]):
        """
        Construct a ListElementError exception

        Args:
            parameter: The Parameter defining the list
            bad: The unrecognized elements
        """
        super().__init__()
        self.parameter = parameter
        self.bad = sorted(bad)

    def __str__(self):
        expected = (
            repr(self.parameter.keywords)
            if self.parameter.keywords
            else self.parameter.element_type.friendly
        )
        return f"Unrecognized list value{'s' if len(self.bad) > 1 else ''} {self.bad!r} given for parameter {self.parameter.name}; expected {expected}"


class PostprocessError(Exception):
    """
    Used by subclasses to report an error during postprocessing of the
    Elasticsearch response document.
    """

    def __init__(self, status: int, message: str, data: JSON = None):
        self.status = status
        self.message = message
        self.data = data

    def __str__(self) -> str:
        return f"Postprocessing error returning {self.status}: {self.message!r} [{self.data}]"


def convert_date(value: str, _) -> datetime:
    """
    Convert a date/time string to a datetime.datetime object.

    Args:
        value: String representation of date/time
        _: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        datetime.datetime object
    """
    try:
        return date_parser.parse(value)
    except Exception:
        raise ConversionError(value, "date/time string")


def convert_username(value: Union[str, None], _) -> Union[str, None]:
    """
    Validate that the user object referenced by the username string exists, and
    return the internal representation of that user.

    We do not want an unauthenticated client to be able to distinguish between
    invalid user" (ConversionError here) and "valid user I can't access" (some
    sort of permission error later). Checking for a valid authentication token
    here allows rejecting any "user" parameter reference by an unauthenticated
    user.

    An authenticated user *can* determine whether a username is valid, and will
    be able to ask for another user's public data with {"user": "name",
    "access": "public"} (or simply "{"user": "name"}, if the authenticated user
    doesn't have rights to "name"'s private data). An authenticated user will
    be given a validation error (BAD_REQUEST/400) if the specified username
    isn't valid and a permission error (FORBIDDEN) if asking for another user's
    private data (without ADMIN role).

    The internal representation is the user row ID as a string.

    Args:
        value: external user representation
        _: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized
        UnverifiedUser: unauthenticated client can't validate a username

    Returns:
        internal username representation
    """
    if isinstance(value, str):
        if not Auth.token_auth.current_user():
            raise UnverifiedUser(value)
        try:
            user = User.query(username=value)
        except Exception:
            pass
        else:
            if user:
                return str(user.id)
    raise ConversionError(value, "username")


def convert_json(value: JSON, parameter: "Parameter") -> JSON:
    """
    Validate a parameter of JSON type.

    Args:
        value: JSON dict
        parameter: Supplies list of allowed JSON keys

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        The JSON dict
    """
    try:
        if json.loads(json.dumps(value)) == value:
            if parameter.keywords:
                bad = []
                for k in value.keys():
                    if not Metadata.is_key_path(k, parameter.keywords):
                        bad.append(k)
                if bad:
                    raise KeywordError(
                        parameter, f"JSON key{'s' if len(bad) > 1 else ''}", bad
                    )
            return value
    except JSONDecodeError:
        pass
    raise ConversionError(value, "JSON")


def convert_string(value: str, _) -> str:
    """
    Verify that the parameter value is a string (e.g., not a JSON dict, or an
    int), and return it.

    Args:
        value: parameter value
        _: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        the input value
    """
    if type(value) is not str:
        raise ConversionError(value, str.__name__)
    return value


def convert_keyword(value: str, parameter: "Parameter") -> str:
    """
    Verify that the parameter value is a string and a member of the
    `valid` list. The match is case-blind and will return the lowercased
    version of the input keyword.

    Keyword matching recognizes a special sort of keyword that roots a
    user-defined "open" secondary namespace controlled by the caller, signaled
    by the ".*" suffix on the keyword: e.g., a keyword of "user.*" will match
    input of "user", "user.contact" and "user.cloud.name".

    Args:
        value: parameter value
        parameter: The Parameter definition (provides valid keywords)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        the input value
    """
    if type(value) is not str:
        raise ConversionError(value, str.__name__)
    input = value.lower()
    if Metadata.is_key_path(input, parameter.keywords):
        return input
    raise KeywordError(parameter, "keyword", [value])


def convert_list(value: List[Any], parameter: "Parameter") -> List[Any]:
    """
    Verify that the parameter value is a list and that each element
    of the list is a valid instance of the referenced element type.

    Args:
        value: parameter value
        parameter: The Parameter definition (provides list element type)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        A new list with normalized elements
    """
    if type(value) is not list:
        raise ConversionError(value, f"List of {parameter.name}")
    etype: "ParamType" = parameter.element_type
    retlist = []
    errlist = []
    for v in value:
        try:
            retlist.append(etype.convert(v, parameter))
        except SchemaError:
            errlist.append(v)
    if errlist:
        raise ListElementError(parameter, errlist)
    return retlist


def convert_access(value: str, parameter: "Parameter") -> str:
    """
    Verify that the parameter value is a case-insensitive access scope keyword:
    either "public" or "private". Return the normalized lowercase form.

    NOTE: This is not implemented as an ENUM because it's expected that we'll
    extend this to support some form of group reference in the future.

    Args:
        value: parameter value
        parameter: The Parameter definition (in this case supplies only
            parameter name for errors)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        the validated access string
    """
    if type(value) is not str:
        raise ConversionError(value, str.__name__)
    v = value.lower()
    if v not in Dataset.ACCESS_KEYWORDS:
        raise KeywordError(
            parameter, "access keyword", [value], keywords=Dataset.ACCESS_KEYWORDS
        )
    return v


class ParamType(Enum):
    """
    Define the possible JSON query parameter keys, and their type.

    The common code can perform conversions on the required parameters with
    known types.
    """

    ACCESS = ("Access", convert_access)
    DATE = ("Date", convert_date)
    JSON = ("Json", convert_json)
    KEYWORD = ("Keyword", convert_keyword)
    LIST = ("List", convert_list)
    STRING = ("String", convert_string)
    USER = ("User", convert_username)

    def __init__(self, name: AnyStr, convert: Callable[[AnyStr], Any]):
        """
        Enum initializer: this uses a mixed-case name string in addition to the
        conversion method simply because with only the Callable value I ran
        into naming issues.
        """
        self.friendly = name
        self.convert = convert

    def __str__(self) -> str:
        return self.name


class Parameter:
    """
    Define the attributes of a parameter using the ParamType ENUM

    Note that a parameter that's "required" must also be non-empty.
    """

    def __init__(
        self,
        name: str,
        type: ParamType,
        *,  # Following are keyword-only
        keywords: List[str] = None,
        element_type: ParamType = None,
        required: bool = False,
    ):
        """
        Initialize a Parameter object describing a JSON parameter with its type
        and attributes.

        Args:
            name: Parameter name
            type: Parameter type
            keywords: List of keywords for ParamType.KEYWORD
            element_type: List element type if ParamType.LIST
            required: whether the parameter is required (defaults to False)
        """
        self.name = name
        self.type = type
        self.keywords = [k.lower() for k in keywords] if keywords else None
        self.element_type = element_type
        self.required = required

    def invalid(self, json: JSON) -> bool:
        """
        Check whether the value of this parameter in the JSON document
        is invalid. A required parameter value must be non-null; a
        parameter that's not required may be absent or null.

        Args:
            json: The client JSON document being validated.

        Returns:
            True if the specified value is unacceptable
        """
        return self.required and (self.name not in json or json[self.name] is None)

    def normalize(self, data: JSONVALUE):
        """
        Validate and normalize user JSON input properties for the API code.

        Args:
            data: Value of the JSON document key

        Returns:
            Normalized format
        """
        return self.type.convert(data, self)

    def __str__(self) -> str:
        return (
            f"Parameter<{self.name}:{self.type}"
            f"{',' + str(self.keywords) if self.type == ParamType.KEYWORD else ''}"
            f"{',' + str(self.element_type) if self.type == ParamType.LIST else ''}"
            f"{',required' if self.required else ''}>"
        )


class Schema:
    """
    Define the client input schema for a server query.

    This provides methods to help validate a JSON client request payload as
    well as centralizing some type conversions.
    """

    def __init__(self, *parameters: Parameter):
        """
        Specify an interface schema as a list of Parameter objects.

        Args:
            parameters: a list of Parameter objects
        """
        self.parameters = {p.name: p for p in parameters}

    def validate(self, json_data: JSON) -> JSON:
        """
        Validate an incoming JSON document against the schema and return a new
        JSON dict with translated values.

        Args:
            json_data: Incoming client JSON document

        Returns:
            New JSON document with validated and possibly translated values
        """
        if not json_data:
            raise InvalidRequestPayload()

        bad_keys = [n for n, p in self.parameters.items() if p.invalid(json_data)]
        if len(bad_keys) > 0:
            raise MissingParameters(bad_keys)

        processed = {}
        for p in json_data:
            tp = self.parameters.get(p)
            processed[p] = tp.normalize(json_data[p]) if tp else json_data[p]
        return processed

    def __contains__(self, key):
        return key in self.parameters

    def __getitem__(self, key):
        return self.parameters[key]

    def __str__(self) -> str:
        return f"Schema<{self.parameters}>"


class API_OPERATION(Enum):
    """
    The standard CRUD REST API operations:

        CREATE: Instantiate a new resource
        READ:   Retrieve the state of a resource
        UPDATE: Modify the state of a resource
        DELETE: Remove a resource

    NOTE: only READ and UPDATE are currently used by Pbench queries.
    """

    CREATE = 1
    READ = 2
    UPDATE = 3
    DELETE = 4


class ApiBase(Resource):
    """
    A base class for Pbench queries that provides common parameter handling
    behavior for specialized subclasses.

    This class extends the Flask Resource class in order to connect the post
    and get methods to Flask's URI routing algorithms. It implements a common
    JSON client payload intake and validation.

    Hooks are defined for subclasses extending this class to handle GET, POST,
    PUT, and DELETE HTTP operations by overriding the abstract _get, _post,
    _put, and _delete methods.
    """

    # We treat the current "access category" of the dataset as user-accessible
    # metadata for the purposes of these APIs even though it's represented as
    # a column on the Dataset model.
    METADATA = Metadata.USER_METADATA + [Dataset.ACCESS, Dataset.OWNER]

    def __init__(
        self,
        config: PbenchServerConfig,
        logger: Logger,
        schema: Schema,
        *,  # following parameters are keyword-only
        role: API_OPERATION = API_OPERATION.READ,
    ):
        """
        Base class constructor.

        Args:
            config: server configuration
            logger: logger object
            schema: API schema: for example,
                    Schema(
                        Parameter("user", ParamType.USER, required=True),
                        Parameter("start", ParamType.DATE)
                    )
            role: specify the API role, defaulting to READ

        NOTE: each class currently only supports a single schema across POST
        and PUT operations. GET (and DELETE?) are assumed not to have/need a
        request payload. If we ever need to change this, we can add a level
        and describe a distinct Schema for each HTTP method.
        """
        super().__init__()
        self.logger = logger
        self.schema = schema
        self.role = role

    def _check_authorization(self, user: Union[str, None], access: Union[str, None]):
        """
        Check whether an API call is able to access data, based on the API's
        authorization header, the requested user, the requested access
        policy, and the API's role.

        If there is no current authenticated API user, only READ operations on
        public data will be allowed.

        If the specified "user" context of the operation is None, we default to
        the authenticated caller, if any; Pbench query operations will do the
        same.

        for API_OPERATION.READ:

            Any call, with or without an authenticated user token, can access
            public data.

            Any authenticated user can access their own private data.

            Any authenticated ADMIN user can access any private data.

        for API_OPERATION.UPDATE:

            An authenticated user is required.

            Any authenticated user can update their own data.

            Any authenticated ADMIN user can update any data.

        Args:
            user: The user parameter to the API, or None
            access: The access parameter to the API, or None

        Raises:
            UnauthorizedAccess The user isn't authorized for the requested
                access.
        """
        authorized_user: User = Auth.token_auth.current_user()
        self.logger.debug(
            "Authorizing {} access for {} to user {} with access {}",
            self.role,
            authorized_user,
            user,
            access,
        )

        # Default user to the authenticated user, if not specified
        if authorized_user and not user:
            user = authorized_user.username
        status = HTTPStatus.OK

        # READ access to public data is always allowed; if we're looking at
        # private data, or non-READ access (create, update, delete) then we
        # need more checks.
        if self.role != API_OPERATION.READ or access == Dataset.PRIVATE_ACCESS:
            if authorized_user is None:
                self.logger.warning(
                    "Attempt to {} user {} data without login", self.role, user
                )
                status = HTTPStatus.UNAUTHORIZED
            elif user != authorized_user.username and not authorized_user.is_admin():
                self.logger.warning(
                    "Unauthorized attempt by {} to {} user {} data",
                    authorized_user,
                    self.role,
                    user,
                )
                status = HTTPStatus.FORBIDDEN
        if status != HTTPStatus.OK:
            raise UnauthorizedAccess(authorized_user, self.role, user, access, status)

    def _get_metadata(
        self, controller: str, name: str, requested_items: List[str]
    ) -> JSON:
        """
        Get requested metadata about a specific Dataset and return a JSON
        fragment that can be added to other data about the Dataset.

        This supports strict Metadata key/value items associated with the
        Dataset as well as selected columns from the Dataset model.

        Args:
            controller: Dataset controller name
            name: Dataset run name
            requested_items: List of metadata key names

        Returns:
            JSON object (Python dict) containing a key-value pair for each
            requested metadata key present on the dataset.
        """
        if not requested_items:
            return {}

        dataset: Dataset = Dataset.attach(controller=controller, name=name)
        metadata = {}
        for i in requested_items:
            if i == Dataset.ACCESS:
                metadata[i] = dataset.access
            elif i == Dataset.OWNER:
                metadata[i] = dataset.owner.username
            elif Metadata.is_key_path(i, Metadata.USER_METADATA):
                try:
                    metadata[i] = Metadata.getvalue(dataset=dataset, key=i)
                except MetadataNotFound:
                    metadata[i] = None
            else:
                raise MetadataBadKey(i)

        return metadata

    def _dispatch(self, method: Callable, request: Request) -> Response:
        """
        This is a common front end for HTTP operations.

        If the class has a parameter schema, and the HTTP operation is not GET
        (which doesn't accept a request payload), we'll validate and normalize
        the request payload here before calling the subclass helper method.

        Args:
            method: A reference to the implementation method
            request: The flask Request object containing payload and headers

        Returns:
            Flask Response object generally constructed implicitly from a JSON
            payload and HTTP status.
        """

        # We don't accept or process a request payload for GET, or if no
        # parameter schema is defined
        if not self.schema or method == self._get:
            return method({}, request)

        try:
            json_data = request.get_json()
        except Exception as e:
            self.logger.warning(
                "{}: Bad JSON in request, {!r}, {!r}",
                self.__class__.__name__,
                str(e),
                request.data,
            )
            abort(HTTPStatus.BAD_REQUEST, message="Invalid request payload")

        try:
            new_data = self.schema.validate(json_data)
        except UnverifiedUser as e:
            self.logger.warning("{}", str(e))
            abort(e.http_status, message=str(e))
        except SchemaError as e:
            self.logger.warning(
                "{}: {} on {!r}", self.__class__.__name__, str(e), json_data
            )
            abort(HTTPStatus.BAD_REQUEST, message=str(e))
        except Exception as e:
            self.logger.exception(
                "Unexpected validation exception in {}: {}",
                e.__class__.__name__,
                str(e),
            )
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                message="INTERNAL ERROR IN VALIDATION",
            )

        # Automatically authorize the operation only if the API schema has the
        # "user" key of type USERNAME; otherwise we assume that authorization
        # is unnecessary or that the API-specific subclass will take care of
        # that in preprocess.
        if "user" in self.schema and self.schema["user"].type is ParamType.USER:
            user = json_data.get("user")  # original username, not user ID
            access = new_data.get("access")  # normalized access policy
            try:
                self._check_authorization(user, access)
            except UnauthorizedAccess as e:
                self.logger.warning("{}", e)
                abort(e.status, message=str(e))
        return method(new_data, request)

    def _get(self, json_data: JSON, request: Request) -> Response:
        """
        ABSTRACT METHOD: override in subclass to perform operation

        Perform the requested GET operation, and handle any exceptions.

        Args:
            json_data: Type-normalized client JSON input
            request: Original incoming Request object

        Returns:
            Response to return to client
        """
        raise NotImplementedError(
            f"Class {self.__class__.__name__} doesn't override abstract _get method"
        )

    def _post(self, json_data: JSON, request: Request) -> Response:
        """
        ABSTRACT METHOD: override in subclass to perform operation

        Perform the requested POST operation, and handle any exceptions.

        Args:
            json_data: Type-normalized client JSON input
            request: Original incoming Request object

        Returns:
            Response to return to client
        """
        raise NotImplementedError(
            f"Class {self.__class__.__name__} doesn't override abstract _post method"
        )

    def _put(self, json_data: JSON, request: Request) -> Response:
        """
        ABSTRACT METHOD: override in subclass to perform operation

        Perform the requested PUT operation, and handle any exceptions.

        Args:
            json_data: Type-normalized client JSON input
            request: Original incoming Request object

        Returns:
            Response to return to client
        """
        raise NotImplementedError(
            f"Class {self.__class__.__name__} doesn't override abstract _put method"
        )

    def _delete(self, json_data: JSON, request: Request) -> Response:
        """
        ABSTRACT METHOD: override in subclass to perform operation

        Perform the requested DELETE operation, and handle any exceptions.

        Args:
            json_data: Type-normalized client JSON input
            request: Original incoming Request object

        Returns:
            Response to return to client
        """
        raise NotImplementedError(
            f"Class {self.__class__.__name__} doesn't override abstract _delete method"
        )

    @Auth.token_auth.login_required(optional=True)
    def get(self):
        """
        Handle an authenticated GET operation on the Resource
        """
        return self._dispatch(self._get, request)

    @Auth.token_auth.login_required(optional=True)
    def post(self):
        """
        Handle an authenticated POST operation on the Resource
        """
        return self._dispatch(self._post, request)

    @Auth.token_auth.login_required(optional=True)
    def put(self):
        """
        Handle an authenticated PUT operation on the Resource
        """
        return self._dispatch(self._put, request)

    @Auth.token_auth.login_required(optional=True)
    def delete(self):
        """
        Handle an authenticated DELETE operation on the Resource
        """
        return self._dispatch(self._delete, request)
