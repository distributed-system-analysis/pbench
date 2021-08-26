import json
from datetime import datetime
from enum import Enum
from http import HTTPStatus
from logging import Logger
from typing import Any, AnyStr, Callable, Dict, List, Union
from flask.wrappers import Request, Response

from dateutil import parser as date_parser
from flask import request
from flask_restful import Resource, abort
from pbench.server import PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.users import User

# A type defined to conform to the semantic definition of a JSON structure
# with Python syntax.
JSONSTRING = str
JSONNUMBER = Union[int, float]
JSONVALUE = Union["JSONOBJECT", "JSONARRAY", JSONSTRING, JSONNUMBER, bool, None]
JSONARRAY = List[JSONVALUE]
JSONOBJECT = Dict[JSONSTRING, JSONVALUE]
JSON = JSONVALUE

# A type defined to allow the preprocess subclass method to provide shared
# context with the assemble and postprocess methods.
CONTEXT = Dict[str, Any]


class UnauthorizedAccess(Exception):
    """
    The user is not authorized for the requested operation on the specified
    resource.
    """

    def __init__(self, user: str, operation: "API_OPERATION", owner: str, access: str):
        self.user = user
        self.operation = operation
        self.owner = owner
        self.access = access

    def __str__(self) -> str:
        return f"User {self.user} is not authorized to {self.operation} a resource owned by {self.owner} with {self.access} access"


class SchemaError(TypeError):
    """
    Generic base class for errors in processing a JSON schema.
    """

    def __init__(self, status: int = HTTPStatus.BAD_REQUEST):
        self.http_status = status


class UnverifiedUser(SchemaError):
    """
    Unverified attempt to access other user data.
    """

    def __init__(self, username: str):
        self.username = username
        super().__init__(status=HTTPStatus.UNAUTHORIZED)

    def __str__(self):
        return f"{self.username} can not be verified"


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
        self.keys = keys

    def __str__(self):
        return f"Missing required parameters: {','.join(self.keys)}"


class ConversionError(SchemaError):
    """
    ConversionError Used to report an invalid parameter type
    """

    def __init__(self, value: Any, expected_type: str, actual_type: str):
        """
        Construct a ConversionError exception

        Args:
            value: The value we tried to convert
            expected_type: The expected type
            actual_type: The actual type
        """
        super().__init__()
        self.value = value
        self.expected_type = expected_type
        self.actual_type = actual_type

    def __str__(self):
        return f"Value {self.value!r} ({self.actual_type}) cannot be parsed as a {self.expected_type}"


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
        return f"Postprocessing error returning {self.status}: '{str(self.message)} [{self.data}]'"


def convert_date(value: str) -> datetime:
    """
    Convert a date/time string to a datetime.datetime object.

    Args:
        value: String representation of date/time
        parameter: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        datetime.datetime object
    """
    try:
        return date_parser.parse(value)
    except Exception:
        raise ConversionError(value, "date/time string", type(value).__name__)


def convert_username(value: str) -> str:
    """
    Convert the external string representation of a username by validating that
    the specified username exists, and returns the desired internal
    representation of that user.

    The internal representation is the user row ID as a string. If the external
    value is None, (which means the API's user parameter is nullable), we
    return None to indicate that instead of attempting to query the User DB.

    Args:
        value: external user representation
        parameter: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        internal username representation or None
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConversionError(value, str.__name__, type(value).__name__)
    try:
        user = Auth().verify_user(value)
    except Exception:
        raise ConversionError(value, "username", type(value).__name__)
    if not user:
        raise UnverifiedUser(value)
    return str(user.id)


def convert_json(value: JSON) -> JSON:
    """
    Process a parameter of JSON type.

    Args:
        value: JSON dict
        parameter: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        The JSON dict
    """
    try:
        if json.loads(json.dumps(value)) != value:
            raise TypeError
    except Exception:
        raise ConversionError(value, "JSON", type(value).__name__) from None
    return value


def convert_string(value: str) -> str:
    """
    Verify that the parameter value is a string (e.g., not a JSON dict, or an
    int), and return it.

    Args:
        value: parameter value
        parameter: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        the input value
    """
    if type(value) is not str:
        raise ConversionError(value, str.__name__, type(value).__name__)
    return value


def convert_access(value: str) -> str:
    """
    Verify that the parameter value is an access scope. Currently this means
    either "public" or "private".

    NOTE: This is not implemented as an ENUM because it's expected that we'll
    extend this to support some form of group reference in the future.

    Args:
        value: parameter value
        parameter: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        the validated access string
    """
    if type(value) is not str:
        raise ConversionError(value, str.__name__, type(value).__name__)
    v = value.lower()
    if v not in Dataset.ACCESS_KEYWORDS:
        raise ConversionError(value, "access", type(value).__name__)
    return v


class ParamType(Enum):
    """
    Define the possible JSON query parameter keys, and their type.

    The common code can perform conversions on the required parameters with
    known types.

    NOTE: In theory, `ACCESS` could be retired in favor of a `KEYWORD`; however
    the plan is that `ACCESS` will evolve to support groups rather than just
    the current "public" and "private" keywords (it would become more like the
    `USER` lookup validator), so it makes sense to keep them separate.
    """

    DATE = ("Date", convert_date)
    USER = ("User", convert_username)
    JSON = ("Json", convert_json)
    STRING = ("String", convert_string)
    ACCESS = ("Access", convert_access)

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
        self, name: AnyStr, type: ParamType, required: bool = False,
    ):
        """
        Initialize a Parameter object describing a JSON parameter with its type
        and attributes.

        Args:
            name: Parameter name
            type: Parameter type
            keywords: List of keywords for ParmType.KEYWORD
            required: whether the parameter is required (default to False)
        """
        self.name = name
        self.type = type
        self.required = required

    def invalid(self, json: JSON) -> bool:
        """
        Check whether the value of this parameter in the JSON document
        is invalid.

        Args:
            json: The client JSON document being validated.

        Returns:
            True if the specified value is unacceptable
        """
        if self.name in json:
            return json[self.name] is None
        else:
            return self.required

    def normalize(self, data: JSONVALUE):
        """
        Validate and normalize user JSON input properties for the API code.

        Args:
            data: Value of the JSON document key

        Returns:
            Normalized format
        """
        return self.type.convert(data)

    def __str__(self) -> str:
        return (
            f"Parameter<{self.name}:{self.type}"
            f"{',' + str(self.keywords) if self.type == ParamType.KEYWORD else ''}"
            f"{',required' if self.required else ''}>"
        )


class Schema:
    """
    Define the client input schema for a server query that's based on
    Elasticsearch.

    This provides methods to help validate a JSON client request payload as
    well as centralizing some type conversions.

    This (and supporting classes above) are part of this module because they're
    currently used only by the ElasticBase class. If they're found later to
    have wider use they can be split out into a separate module.
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
    A base class for Elasticsearch queries that allows subclasses to provide
    custom pre- and post- processing.

    This class extends the Flask Resource class in order to connect the post
    and get methods to Flask's URI routing algorithms. It implements a common
    JSON client payload intake and validation, along with the mechanism for
    calling Elasticsearch and processing errors.

    Hooks are defined for subclasses extending this class to "preprocess"
    the query, to "assemble" the Elasticsearch request payload from Pbench
    server data and the client's JSON payload, and to "postprocess" a
    successful response payload from Elasticsearch.

    Note that "preprocess" can provide context that's passed to the assemble
    and postprocess methods.
    """

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

        NOTE: each class currently only supports one HTTP method, so we can
        describe only one set of parameters. If we ever need to change this,
        we can add a level and describe distinct parameters for each method.
        """
        super().__init__()
        self.logger = logger
        self.schema = schema
        self.role = role

    def _check_authorization(self, user: str, access: str):
        """
        Check whether an API call is able to access data, based on the API's
        authorization header, the requested user, the requested access
        policy, and the API's role.

        If "user" is None, then the request is unauthenticated. READ operations
        may be allowed, UPDATE and DELETE operations will not be allowed.

        If "access" is None, READ will assume we're looking for access only to
        public datasets.

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
        authorized = True
        self.logger.debug(
            "Authorizing {} access for {} to user {} with access {}",
            self.role,
            authorized_user,
            user,
            access,
        )
        if self.role != API_OPERATION.READ or access == Dataset.PRIVATE_ACCESS:
            if authorized_user is None:
                self.logger.warning(
                    "Attempt to {} user {} data without login", self.role, user
                )
                authorized = False
            elif user != authorized_user.username and not authorized_user.is_admin():
                self.logger.warning(
                    "Unauthorized attempt by {} to {} user {} data",
                    authorized_user,
                    self.role,
                    user,
                )
                authorized = False
        if not authorized:
            raise UnauthorizedAccess(authorized_user, self.role, user, access)

    def _dispatch(self, method: Callable, request: Request) -> Response:
        """
        This is a common front end for HTTP operations, which will validate and
        normalize the request JSON document if there's a class schema and the
        operation isn't GET (which doesn't support a request payload).

        Args:
            method: A reference to the implementation method
            request: The flask Request object containing payload and headers

        Returns:
            Flask Response object generally constructed implicitly from a JSON
            payload and HTTP status.
        """
        json_data = request.get_json(silent=True)
        if self.schema and method != self._get:
            try:
                new_data = self.schema.validate(json_data)
            except UnverifiedUser as e:
                self.logger.warning("{}", str(e))
                abort(HTTPStatus.FORBIDDEN, message=str(e))
            except SchemaError as e:
                self.logger.warning(
                    "{}: {} on {!r}", self.__class__.__name__, str(e), json_data
                )
                abort(HTTPStatus.BAD_REQUEST, message=str(e))
            except Exception as e:
                self.logger.exception("POST unexpected {}: {}", e.__class__.__name__, e)
                abort(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message="INTERNAL ERROR IN VALIDATION",
                )

            # TODO: Is this specific to ElasticBase???
            # Maybe a _validation_hook() method?? Or simply deferred to _call()?

            # Automatically authorize the operation only if the API schema has the
            # "user" key; otherwise we assume that authorization is unnecessary, or
            # that the API-specific subclass will take care of that in preprocess.
            if "user" in self.schema:
                user = json_data.get("user")  # original username, not user ID
                access = new_data.get("access")  # normalized access policy
                try:
                    self._check_authorization(user, access)
                except UnauthorizedAccess as e:
                    self.logger.warning("{}", e)
                    abort(HTTPStatus.FORBIDDEN, message="Not Authorized")
            return method(new_data, request)
        else:
            return method(json_data, request)

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
        Handle a GET operation on the Resource
        """
        return self._dispatch(self._get, request)

    @Auth.token_auth.login_required(optional=True)
    def post(self):
        """
        Handle a Pbench server POST operation that will involve a call to the
        server's configured Elasticsearch instance. The assembly and
        post-processing of the Elasticsearch query are handled by the
        subclasses through the assemble() and postprocess() methods;
        we do basic parameter validation and conversions here.

        Each subclass provides a schema for allowed JSON parameters: this
        code processes each JSON parameter in the dict to perform type
        validation/conversion where necessary. Missing "required" parameters
        and any parameter with a null value are rejected. Parameters that
        are not in the class schema are ignored but logged.

        If the request does not contain the user field, it will be interpreted
        as a public dataset query. [TODO: See issue #2370 for more context on
        plans for "user" vs "access" in queries.]
        """
        return self._dispatch(self._post, request)

    @Auth.token_auth.login_required(optional=True)
    def put(self):
        """
        Handle a PUT operation on the Resource
        """
        return self._dispatch(self._put, request)

    @Auth.token_auth.login_required(optional=True)
    def delete(self):
        """
        Handle a DELETE operation on the Resource
        """
        return self._dispatch(self._delete, request)
