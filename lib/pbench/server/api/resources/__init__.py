from datetime import datetime
from enum import auto, Enum
from http import HTTPStatus
import json
from json.decoder import JSONDecodeError
from logging import Logger
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Union

from dateutil import parser as date_parser
from flask import request
from flask.wrappers import Request, Response
from flask_restful import Resource, abort
from sqlalchemy.orm.query import Query

from pbench.server import JSON, JSONOBJECT, JSONVALUE, PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetNotFound,
    Metadata,
    MetadataBadKey,
    MetadataNotFound,
)
from pbench.server.database.models.users import User


class APIAbort(Exception):
    """
    Used to report an error and abort if there is a failure in processing of API request.
    """

    def __init__(self, http_status: int, message: str = None):
        self.http_status = http_status
        self.message = message if message else HTTPStatus(http_status).phrase

    def __repr__(self) -> str:
        return f"API error {self.http_status} : {str(self)}"

    def __str__(self) -> str:
        return self.message


class UnauthorizedAccess(APIAbort):
    """
    The user is not authorized for the requested operation on the specified
    resource.
    """

    def __init__(
        self,
        user: Union[User, None],
        operation: "API_OPERATION",
        owner: Union[str, None],
        access: Union[str, None],
        http_status: int = HTTPStatus.FORBIDDEN,
    ):
        super().__init__(http_status=http_status)
        self.user = user
        self.operation = operation
        self.owner = owner
        self.access = access

    def __str__(self) -> str:
        return f"{'User ' + self.user.username if self.user else 'Unauthenticated client'} is not authorized to {self.operation.name} a resource owned by {self.owner} with {self.access} access"


class SchemaError(APIAbort):
    """
    Generic base class for errors in processing a JSON schema.
    """

    def __init__(self, http_status: int = HTTPStatus.BAD_REQUEST):
        super().__init__(http_status=http_status)

    def __str__(self) -> str:
        return "Generic schema validation error"


class UnverifiedUser(SchemaError):
    """
    Attempt by an unauthenticated client to reference a username in a query. An
    unauthenticated client does not have the right to look up any username.

    HTTPStatus.UNAUTHORIZED tells the client that the operation might succeed
    if the request is retried with authentication. (A UI might redirect to a
    login page.)
    """

    def __init__(self, username: str):
        super().__init__(http_status=HTTPStatus.UNAUTHORIZED)
        self.username = username

    def __str__(self):
        return f"Requestor is unable to verify username {self.username!r}"


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

    def __init__(self, keys: List[str]):
        super().__init__()
        self.keys = sorted(keys)

    def __str__(self):
        return f"Missing required parameters: {','.join(self.keys)}"


class BadQueryParam(SchemaError):
    """
    One or more unrecognized URL query parameters were specified.
    """

    def __init__(self, keys: List[str]):
        super().__init__()
        self.keys = sorted(keys)

    def __str__(self):
        return f"Unknown URL query keys: {','.join(self.keys)}"


class RepeatedQueryParam(SchemaError):
    """
    A URL query parameter key was repeated, but Pbench supports only one value.
    """

    def __init__(self, key: str):
        super().__init__()
        self.key = key

    def __str__(self):
        return f"Repeated URL query key '{self.key}'"


class ConversionError(SchemaError):
    """
    Used to report an invalid parameter type
    """

    def __init__(self, value: Any, expected_type: str, **kwargs):
        """
        Construct a ConversionError exception

        Args:
            value: The value we tried to convert
            expected_type: The expected type
            kwargs: Optional SchemaError parameters
        """
        super().__init__(**kwargs)
        self.value = value
        self.expected_type = expected_type

    def __str__(self):
        return f"Value {self.value!r} ({type(self.value).__name__}) cannot be parsed as a {self.expected_type}"


class DatasetConversionError(SchemaError):
    """
    Used to report an invalid dataset name.
    """

    def __init__(self, value: str, **kwargs):
        """
        Construct a DatasetConversionError exception. This is modeled after
        DatasetNotFound, but is within the SchemaError exception hierarchy.

        Args:
            value: The value we tried to convert
            kwargs: Optional SchemaError parameters
        """
        super().__init__(http_status=HTTPStatus.NOT_FOUND, **kwargs)
        self.value = value

    def __str__(self):
        return f"Dataset {self.value!r} not found"


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
        key = "keywords" if not self.parameter.key_path else "namespaces"
        return f"Unrecognized {self.expected_type} {self.unrecognized!r} given for parameter {self.parameter.name}; allowed {key} are {self.keywords!r}"


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
    "invalid user" (ConversionError here) and "valid user I can't access" (some
    sort of permission error later). Checking for a valid authentication token
    here allows rejecting any USERNAME parameter passed by an unauthenticated
    user with UNAUTHORIZED/401

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
    if not isinstance(value, str):
        raise ConversionError(value, "username")
    if not Auth.token_auth.current_user():
        raise UnverifiedUser(value)

    try:
        user = User.query(username=value)
    except Exception:
        raise ConversionError(
            value, "username", http_status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

    if not user:
        raise ConversionError(value, "username", http_status=HTTPStatus.NOT_FOUND)

    return str(user.id)


def convert_dataset(value: str, _) -> Dataset:
    """
    Convert a dataset name string to a Dataset object reference.

    Args:
        value: String representation of dataset name
        _: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        Dataset
    """
    try:
        return Dataset.query(name=value)
    except DatasetNotFound as e:
        raise DatasetConversionError(value) from e


def convert_json(value: JSONOBJECT, parameter: "Parameter") -> JSONOBJECT:
    """
    Validate a parameter of JSON type. If the Parameter object defines a list
    of keywords, the JSON key values are validated against that list. If the
    Parameter key_path attribute is set, then only the first element of a
    dotted path (e.g., "user" for "user.contact.email") is validated.

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
                    if parameter.key_path:
                        if not Metadata.is_key_path(k, parameter.keywords):
                            bad.append(k)
                    elif k not in parameter.keywords:
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


def convert_int(value: Union[int, str], _) -> int:
    """
    Verify that the parameter value is either int or string and
    if string then convert it to an int.

    Args:
        value: parameter value
        _: The Parameter definition (not used)

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        the input value
    """
    if type(value) is int:
        return value
    elif type(value) is str:
        try:
            return int(value)
        except ValueError:
            pass
    raise ConversionError(value, int.__name__)


def convert_keyword(value: str, parameter: "Parameter") -> str:
    """
    Verify that the parameter value is a string and a member of the
    `valid` list. The match is case-blind and will return the lowercased
    version of the input keyword. If there are no keywords defined, the
    input is lowercased and returned without validation.

    Keyword matching recognizes a "path" keyword where validation occurs only
    on the first element of a dotted path (e.g., "user.contact.email" matches
    against "user"). This is signaled by the key_path attribute of the
    Parameter object.

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
    if not parameter.keywords:
        return input
    elif parameter.key_path and Metadata.is_key_path(input, parameter.keywords):
        return input
    elif input in parameter.keywords:
        return input
    raise KeywordError(parameter, "keyword", [value])


def convert_list(value: Union[str, List[str]], parameter: "Parameter") -> List[Any]:
    """
    Verify that the parameter value is a list and that each element
    of the list is a valid instance of the referenced element type.

    Args:
        value: parameter value -- either a list or a string which is
            split on commas into a list.
        parameter: The Parameter definition (provides list element type)

    NOTE: the capability of splitting a string is primarily designed to allow
    more conveniently listing metadata keys, especially in URL query parameters
    as `?metadata=a,b` rather than `?metadata=a&metadata=b`, but it can be
    used for any list where the individual elements can't contain a comma.

    Raises:
        ConversionError: input can't be validated or normalized

    Returns:
        A new list with normalized elements
    """
    values = None
    if parameter.string_list:
        if type(value) is str:
            values = value.split(parameter.string_list)
        elif type(value) is list:
            values = [x for e in value for x in e.split(parameter.string_list)]
    elif type(value) is list:
        values = value
    if values is None:
        raise ConversionError(value, f"List of {parameter.name}")
    etype: Union["ParamType", None] = parameter.element_type
    errlist = []
    if etype:
        retlist = []
        for v in values:
            try:
                retlist.append(etype.convert(v, parameter))
            except SchemaError:
                errlist.append(v)
    else:
        retlist = values  # No need for conversion
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
    DATASET = ("Dataset", convert_dataset)
    DATE = ("Date", convert_date)
    INT = ("Int", convert_int)
    JSON = ("Json", convert_json)
    KEYWORD = ("Keyword", convert_keyword)
    LIST = ("List", convert_list)
    STRING = ("String", convert_string)
    USER = ("User", convert_username)

    def __init__(self, name: str, convert: Callable[[Any, "Parameter"], Any]):
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
        keywords: Union[List[str], None] = None,
        element_type: Union[ParamType, None] = None,
        required: bool = False,
        key_path: bool = False,
        string_list: Union[str, None] = None,
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
            key_path: keyword value can be a dotted path where only the first
                element matches the keyword list.
            string_list: if a delimiter is specified, individual string values
                will be split into lists.
        """
        self.name = name
        self.type = type
        self.keywords = [k.lower() for k in keywords] if keywords else None
        self.element_type = element_type
        self.required = required
        self.key_path = key_path
        self.string_list = string_list

    def invalid(self, json: JSONOBJECT) -> bool:
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


class ParamSet(NamedTuple):
    parameter: Parameter
    value: Any


class API_METHOD(Enum):
    DELETE = auto()
    GET = auto()
    HEAD = auto()
    POST = auto()
    PUT = auto()


class API_OPERATION(Enum):
    """
    The standard CRUD REST API operations:

        CREATE: Instantiate a new resource
        READ:   Retrieve the state of a resource
        UPDATE: Modify the state of a resource
        DELETE: Remove a resource

    NOTE: only READ and UPDATE are currently used by Pbench queries.
    """

    CREATE = auto()
    READ = auto()
    UPDATE = auto()
    DELETE = auto()


class API_AUTHORIZATION(Enum):
    NONE = auto()
    DATASET = auto()
    USER_ACCESS = auto()


class ApiParams(NamedTuple):
    body: Optional[JSONOBJECT]
    query: Optional[JSONOBJECT]
    uri: Optional[JSONOBJECT]


class ApiAuthorization(NamedTuple):
    user: Optional[str]
    access: Optional[str]
    role: API_OPERATION


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

    def validate(self, json_data: JSONOBJECT) -> JSONOBJECT:
        """
        Validate an incoming JSON document against the schema and return a new
        JSON dict with translated values.

        Args:
            json_data: Incoming client JSON document

        Returns:
            New JSON document with validated and possibly translated values
        """

        if not json_data:

            missing = [p.name for p in self.parameters.values() if p.required]
            if missing:
                raise MissingParameters(missing)

            return {}

        bad_keys = [n for n, p in self.parameters.items() if p.invalid(json_data)]
        if len(bad_keys) > 0:
            raise MissingParameters(bad_keys)

        processed = {}
        for p in json_data:
            tp = self.parameters.get(p)
            processed[p] = tp.normalize(json_data[p]) if tp else json_data[p]
        return processed

    def get_param_by_type(
        self, dtype: ParamType, params: Optional[JSONOBJECT]
    ) -> Optional[ParamSet]:
        """
        Find a parameter of the desired type.

        Search the schema for the first Parameter of the desired type,
        returning the parameter definition and the assigned value for that
        parameter.

        Args
            dtype:  The desired datatype (e.g., DATASET or USER)
            params: The API parameter set

        Returns:
            The parameter and its value, or None if not found
        """
        for n, p in self.parameters.items():
            if p.type is dtype:
                return ParamSet(
                    parameter=p, value=params.get(p.name) if params else None
                )
        return None

    def __contains__(self, key):
        return key in self.parameters

    def __getitem__(self, key):
        return self.parameters[key]

    def __str__(self) -> str:
        return f"Schema<{self.parameters}>"


class ApiSchema:
    """
    A collection of Schema objects targeted for specific HTTP operations that
    are supported by an API class.
    """

    def __init__(
        self,
        method: API_METHOD,
        operation: API_OPERATION,
        body_schema: Optional[Schema] = None,
        query_schema: Optional[Schema] = None,
        uri_schema: Optional[Schema] = None,
        *,
        authorization: API_AUTHORIZATION = API_AUTHORIZATION.NONE,
    ):
        """
        Construct an ApiSchema encapsulating a set of schema objects separating
        URI parameters from query parameters from JSON body parameters that
        apply to a particular HTTP method.

        Args:
            method: API method
            operation:  CRUD operation code
            body_schema:    Definition of parameters received through a JSON
                            body.
            query_schema:   Definition of parameters received through query
                            parameters.
            uri_schema:     Definition of parameters received through Flask URI
                            templates.
            authorization:  How to authorize access to this API method
        """
        self.method = method
        self.operation = operation
        self.body_schema = body_schema
        self.query_schema = query_schema
        self.uri_schema = uri_schema
        self.authorization = authorization

    def get_param_by_type(
        self, dtype: ParamType, params: Optional[ApiParams]
    ) -> Optional[ParamSet]:
        """
        Find a parameter of the desired type.

        This is a wrapper around the Schema method to encapsulate searching
        across the URI parameter schema, then the query parameter schema, and
        finally the JSON body schema for the first occurrence of a Parameter
        of the desired type.

        Args
            dtype:  The desired datatype (e.g., DATASET or USER)
            params: The API parameter set

        Returns:
            The parameter and its value, or None if not found
        """
        if self.body_schema:
            p = self.body_schema.get_param_by_type(
                dtype, params.body if params else None
            )
            if p:
                return p
        if self.query_schema:
            p = self.query_schema.get_param_by_type(
                dtype, params.query if params else None
            )
            if p:
                return p
        if self.uri_schema:
            p = self.uri_schema.get_param_by_type(dtype, params.uri if params else None)
            if p:
                return p
        return None

    def validate(self, params: ApiParams) -> ApiParams:
        """
        Validate API parameters against each of the appropriate schemas,
        separated as URI parameters, query parameters, and JSON payload.

        Args
            params:   The API parameter set

        Returns:
            Converted and validated API parameter set
        """
        body: Optional[JSONOBJECT] = None
        query: Optional[JSONOBJECT] = None
        uri: Optional[JSONOBJECT] = None

        if self.body_schema:
            body = self.body_schema.validate(params.body)
        if self.query_schema:
            query = self.query_schema.validate(params.query)
        if self.uri_schema:
            uri = self.uri_schema.validate(params.uri)

        return ApiParams(body=body, query=query, uri=uri)

    def authorize(self, params: ApiParams) -> Optional[ApiAuthorization]:
        """
        Using the API schema's designated authorization source, provide the
        necessary information for the caller to authorize access.

        AUTHORIZATION.DATASET: Used when the API wants to authorize access to a
            specific dataset, using the dataset owner and access property. The
            ApiSchema must contain a parameter of type ParamType.DATASET which
            must have a value.
        AUTHORIZATION.USER_ACCESS: Used when authorizing a search for datasets
            with specific ownership and access properties.The ApiSchema must
            contain a parameter of type ParamType.USER and one of
            ParamType.ACCESS. Unspecified values will be reported as None.

        Args
            params:   The validated and converted parameter set for the API.

        Returns
            The values for username and access policy to use for authorization.
        """
        if self.authorization == API_AUTHORIZATION.DATASET:
            ds = self.get_param_by_type(ParamType.DATASET, params)
            if ds:
                return ApiAuthorization(
                    user=str(ds.value.owner_id),
                    access=ds.value.access,
                    role=self.operation,
                )
            return None
        elif self.authorization == API_AUTHORIZATION.USER_ACCESS:
            user = self.get_param_by_type(ParamType.USER, params)
            access = self.get_param_by_type(ParamType.ACCESS, params)
            return ApiAuthorization(
                user=user.value, access=access.value, role=self.operation
            )
        return None


class ApiSchemaSet:
    def __init__(self, *schemas: ApiSchema):
        """
        Construct a dict of schemas accessable by API method

        Args:
            schemas:    A list of schemas for each HTTP method supported by an
                        API class.
        """
        self.schemas: Dict[API_METHOD, ApiSchema] = {s.method: s for s in schemas}

    def __getitem__(self, key: API_METHOD):
        return self.schemas.get(key)

    def __iter__(self):
        return iter(self.schemas)

    def __contains__(self, item):
        return item in self.schemas

    def get_param_by_type(
        self, method: API_METHOD, dtype: ParamType, params: Optional[ApiParams]
    ) -> Optional[ParamSet]:
        """
        Find the first relevant parameter of the desired type.

        This uses the "method" parameter to select the appropriate ApiSchema
        for the active API, and then searches for the first Parameter of the
        specified type defined for that API method.

        Args
            method: The API method to be authorized
            dtype:  The desired datatype (e.g., DATASET or USER)
            params: The API parameter set

        Returns:
            The parameter and its value, or None if not found
        """
        return self.schemas[method].get_param_by_type(dtype, params)

    def validate(self, method: API_METHOD, args: ApiParams) -> ApiParams:
        """
        Validate the parameter schema based on the HTTP method used by the
        client.

        If there is no schema defined, this method will assume that there are
        no client parameters to validate or convert, and return an empty set of
        parameters.

        NOTE: This allows an API that has no parameters defined; e.g., to get
        global information.

        Args:
            method: The HTTP method (GET, PUT, POST, DELETE)
            args:   An argument set to validate against the selected schema
        """
        if method in self.schemas:
            return self.schemas[method].validate(args)
        else:
            return ApiParams(body=None, query=None, uri=None)

    def authorize(
        self, method: API_METHOD, args: ApiParams
    ) -> Optional[ApiAuthorization]:
        """
        Determine how API validation should deal with client authorization for
        the selected API schema.

        This is a wrapper around the ApiSchema method to encapsulate selecting
        the proper schema.

        Args
            method: The API method to be authorized
            args:   The API parameter set

        Returns:
            The values for username and access policy to use for authorization.
        """
        if method in self.schemas:
            return self.schemas[method].authorize(args)
        else:
            return None


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

    def __init__(self, config: PbenchServerConfig, logger: Logger, *schemas: ApiSchema):
        """
        Base class constructor.

        Args:
            config: server configuration
            logger: logger object
            schemas: ApiSchema objects to provide parameter validation for for
                    various HTTP methods the API module supports. For example,
                    for GET, PUT, and DELETE.
        """
        super().__init__()
        self.config = config
        self.logger = logger
        self.schemas = ApiSchemaSet(*schemas)

    def _gather_query_params(self, request: Request, schema: Schema) -> JSONOBJECT:
        """
        This collects query parameters (?key or &key) provided by the caller on
        the URL.

        Note that a multi-valued query parameter can be specified *either* by
        a comma-separated single string value *or* by a list of individual
        values, not both.

        Args:
            request:    The HTTP Request object containing query parameters
            schema:     The Schema definition

        Raises:
            RepeatedQueryParam: A query parameter for which we support only one
                value was repeated in the URL.
            BadQueryParam: One or more unsupported query parameter keys were
                specified.

        Returns:
            The resulting JSON object
        """
        json = {}
        badkey = []
        for key in request.args.keys():
            if key in schema:
                values = request.args.getlist(key)
                if schema[key].type == ParamType.LIST:
                    json[key] = values
                elif len(values) == 1:
                    json[key] = values[0]
                else:
                    raise RepeatedQueryParam(key)
            else:
                badkey.append(key)

        if badkey:
            raise BadQueryParam(badkey)

        return json

    def _check_authorization(
        self,
        user_id: Optional[str],
        access: Optional[str],
        role: API_OPERATION,
    ):
        """
        Check whether an API call is able to access data, based on the API's
        authorization header, the requested user, the requested access
        policy, and the API's role.

        If there is no current authenticated client, only READ operations on
        public data will be allowed.

        for API_OPERATION.READ:

            Any call, with or without an authenticated user token, can access
            public data.

            Any authenticated user can access their own private data.

            Any authenticated ADMIN user can access any private data.

        for API_OPERATION.UPDATE, API_OPERATION.DELETE:

            An authenticated user is required.

            Any authenticated user can update/delete their own data.

            Any authenticated ADMIN user can update/delete any data.

        Args:
            user_id: The client's requested user ID (as a string), or None
            access: The client's requested access parameter, or None
            check_role: Override self.role for access check

        Raises:
            UnauthorizedAccess: The user isn't authorized for the requested
            access. One of two HTTP status values are encoded:
                HTTP 401/UNAUTHORIZED: No user was authenticated, meaning
                    that login is required to perform the operation.
                HTTP 402/FORBIDDEN: The authenticated user does not have
                    rights to the specified combination of API ROLE, USER,
                    and ACCESS.
        """
        authorized_user: User = Auth.token_auth.current_user()
        username = "none"
        if user_id:
            user = User.query(id=user_id)
            if user:
                username = user.username
            else:
                self.logger.error(
                    "Parser user ID {} not found in User database", user_id
                )
        self.logger.debug(
            "Authorizing {} access for {} to user {} ({}) with access {}",
            role,
            authorized_user,
            username,
            user_id,
            access,
        )

        # Accept or reject the described operation according to the following
        # rules:
        #
        # 1) An ADMIN user can do anything.
        # 2) An unauthenticated client can't perform any operation on PRIVATE
        #    data, nor any operation other than READ on PUBLIC data;
        # 3) The "user" parameter can be omitted only for READ operations,
        #    which will be defaulted according to the visibility of the
        #    authenticated client.
        # 4) An authenticated client cannot mutate data owned by a different
        #    user, nor READ private data owned by another user.
        if role == API_OPERATION.READ and access == Dataset.PUBLIC_ACCESS:
            # We are reading public data: this is always allowed.
            pass
        else:
            # ROLE is UPDATE, CREATE, DELETE or ACCESS is private; we need to
            # evaluate access rights to determine whether to allow the request
            if authorized_user is None:
                # An unauthenticated user is never allowed to access private
                # data nor to perform an potential mutation of data: REJECT
                self.logger.warning(
                    "Attempt to {} user {} data without login", role, username
                )
                raise UnauthorizedAccess(
                    authorized_user,
                    role,
                    username,
                    access,
                    HTTPStatus.UNAUTHORIZED,
                )
            elif role != API_OPERATION.READ and user_id is None:
                # No target user is specified, so we won't allow mutation of
                # data: REJECT
                self.logger.warning(
                    "Unauthorized attempt by {} to {} data with defaulted user",
                    authorized_user,
                    role,
                )
                raise UnauthorizedAccess(
                    authorized_user, role, username, access, HTTPStatus.FORBIDDEN
                )
            elif (
                user_id
                and user_id != str(authorized_user.id)
                and not authorized_user.is_admin()
            ):
                # We are mutating data, or reading private data, so the
                # authenticated user must either be the owner of the data or
                # must have ADMIN role: REJECT
                self.logger.warning(
                    "Unauthorized attempt by {} to {} user {} data",
                    authorized_user,
                    role,
                    username,
                )
                raise UnauthorizedAccess(
                    authorized_user, role, username, access, HTTPStatus.FORBIDDEN
                )
            else:
                # We have determined that there is an authenticated user with
                # legitimate access: the data is public and the operation is
                # READ, the user owns the data, or the user has ADMIN role.
                pass

    def _build_sql_query(
        self, owner_id: Optional[str], access: Optional[str], base_query: Query
    ) -> Query:
        """
        Extend a SQLAlchemy Query with additional terms applying specified
        owner and access constraints from the parameters JSON.

        NOTE: This method is not responsible for authorization checks; that's
        done by the `ApiBase._check_authorization()` method. This method is
        only concerned with generating a query to restrict the results to the
        set matching authorized user and access values.

        Specific cases for user and access values are described below. The
        cases marked "UNAUTHORIZED" are "default" behaviors where we expect
        that authorization checks will block API calls before reaching this
        code.

            {}: defaulting both user and access
                All private + public regardless of owner

                ADMIN: all datasets
                AUTHENTICATED as drb: owner:drb OR access:public
                UNAUTHENTICATED (or non-drb): access:public

            {"user": "drb"}: defaulting access
                All datasets owned by "drb"

                ADMIN, AUTHENTICATED as drb: owner:drb
                UNAUTHENTICATED (or non-drb): owner:drb AND access:public

            {"user": "drb, "access": "private"}: private drb
                All datasets owned by "drb" with "private" access

                owner:drb AND access:private
                NOTE(UNAUTHORIZED): owner:drb and access:public

            {"user": "drb", "access": "public"}: public drb
                All datasets owned by "drb" with "public" access

                NOTE: unauthenticated users are not allowed to query by
                username, and shouldn't get here, but the query is
                technically correct if we allowed it.

                owner:drb AND access:public

            {"access": "private"}: private data
                All datasets with "private" access regardless of user

                ADMIN: all access:private
                AUTHENTICATED as "drb": owner:"drb" AND access:private
                NOTE(UNAUTHORIZED): access:public

            {"access": "public"}: public data
                All datasets with "public" access

                access:public

        Args:
            owner_id: Pbench user ID to restrict search to datasets owned by
                a specific user.
            access: Access category, "public" or "private" to restrict
                search to datasets with a specific access category.
            base_query: A SQLAlchemy Query object to be extended with user and
                access terms as appropriate

        Returns:
            An SQLAlchemy Query object that may include additional query terms
        """
        authorized_user: User = Auth.token_auth.current_user()
        authorized_id = str(authorized_user.id) if authorized_user else None
        is_admin = authorized_user.is_admin() if authorized_user else False
        query = base_query

        self.logger.debug(
            "QUERY auth ID {}, user {!r}, access {!r}, admin {}",
            authorized_id,
            owner_id,
            access,
            is_admin,
        )

        user_term = False

        # IF we're looking at a user we're not authorized to see (either the
        # call is unauthenticated, or authenticated as a non-ADMIN user trying
        # to reference a different user), then we're only allowed to see PUBLIC
        # data; private data requests aren't allowed, and we expect these cases
        # to fail with appropriate permission errors (401 or 403) before we
        # reach this code.
        #
        # ELSE IF we're looking for a specific access category, add the query
        # term.
        #
        # ELSE IF this is a {} query from a non-ADMIN user, add a "disjunction"
        # (OR) covering all the user's own data plus all public data.
        #
        # ELSE this must be an admin user looking for data owned by a specific
        # user (there's no access parameter, and possibly no user parameter),
        # and we'll pass through the query either with the specified user
        # constraint or with no constraint at all.
        if not authorized_user or (
            owner_id and owner_id != authorized_id and not is_admin
        ):
            query = query.filter(Dataset.access == Dataset.PUBLIC_ACCESS)
            self.logger.debug("QUERY: not self public")
        elif access:
            query = query.filter(Dataset.access == access)
            if not owner_id and access == Dataset.PRIVATE_ACCESS and not is_admin:
                query = query.filter(Dataset.owner_id == authorized_id)
                user_term = True
            self.logger.debug("QUERY: user: {}, access: {}", authorized_id, access)
        elif not owner_id and not is_admin:
            query = query.filter(
                (Dataset.owner_id == authorized_id)
                | (Dataset.access == Dataset.PUBLIC_ACCESS)
            )
            user_term = True
            self.logger.debug("QUERY: self ({}) + public", authorized_user.username)
        else:
            # Either "user" was specified and will be added to the filter,
            # or client is ADMIN and no access restrictions are required.
            self.logger.debug(
                "QUERY: default, user: {}", owner_id if owner_id else authorized_user
            )

        # If a user is specified, and we haven't already added a user term, add
        # it now.
        if owner_id and not user_term:
            query = query.filter(Dataset.owner_id == owner_id)

        return query

    def _get_dataset_metadata(
        self, dataset: Dataset, requested_items: List[str]
    ) -> JSON:
        """
        Get requested metadata about a specific Dataset and return a JSON
        fragment that can be added to other data about the Dataset.

        This supports strict Metadata key/value items associated with the
        Dataset as well as selected columns from the Dataset model.

        Args:
            dataset: Dataset object
            requested_items: List of metadata key names

        Returns:
            JSON object (Python dict) containing a key-value pair for each
            requested metadata key present on the dataset.
        """
        if not requested_items:
            return {}

        metadata = {}
        for i in requested_items:
            if Metadata.is_key_path(i, Metadata.METADATA_KEYS):
                native_key = Metadata.get_native_key(i)
                user: Optional[User] = None
                if native_key == Metadata.USER:
                    user = Auth.token_auth.current_user()
                try:
                    metadata[i] = Metadata.getvalue(dataset=dataset, key=i, user=user)
                except MetadataNotFound:
                    metadata[i] = None
            else:
                raise MetadataBadKey(i)

        return metadata

    def _get_metadata(self, name: str, requested_items: List[str]) -> JSON:
        """
        Get requested metadata about a specific Dataset and return a JSON
        fragment that can be added to other data about the Dataset.

        This supports strict Metadata key/value items associated with the
        Dataset as well as selected columns from the Dataset model.

        Args:
            name: Dataset run name
            requested_items: List of metadata key names

        Returns:
            JSON object (Python dict) containing a key-value pair for each
            requested metadata key present on the dataset.
        """
        dataset: Dataset = Dataset.query(name=name)
        return self._get_dataset_metadata(dataset, requested_items)

    def _dispatch(
        self,
        method: API_METHOD,
        request: Request,
        uri_params: Optional[JSONOBJECT] = None,
    ) -> Response:
        """
        This is a common front end for HTTP operations.

        If the class has a parameter schema, and the HTTP operation is not GET
        (which doesn't accept a request payload), we'll validate and normalize
        the request payload here before calling the subclass helper method.

        Args:
            method: The API HTTP method
            request: The flask Request object containing payload and headers
            uri_params: URI encoded keyword-arg supplied by the Flask
                framework

        Returns:
            Flask Response object generally constructed implicitly from a JSON
            payload and HTTP status.
        """

        api_name = self.__class__.__name__

        self.logger.info("In {} {}", method, api_name)

        if method is API_METHOD.GET:
            execute = self._get
        elif method is API_METHOD.PUT:
            execute = self._put
        elif method is API_METHOD.POST:
            execute = self._post
        elif method is API_METHOD.DELETE:
            execute = self._delete
        else:
            abort(
                HTTPStatus.METHOD_NOT_ALLOWED,
                message=HTTPStatus.METHOD_NOT_ALLOWED.phrase,
            )

        if self.schemas[method]:
            body_params = None
            query_params = None

            # If there's a JSON payload, parse it, and fail if parsing fails.
            # If there's no payload and the API requires JSON body parameters,
            # then the schema validation will diagnose later.
            if request.data and request.mimetype == "application/json":
                try:
                    body_params = request.get_json()
                except Exception as e:
                    abort(
                        HTTPStatus.BAD_REQUEST,
                        message=f"Invalid request payload: {str(e)!r}",
                    )

            try:
                if self.schemas[method].query_schema:
                    query_params = self._gather_query_params(
                        request, self.schemas[method].query_schema
                    )

                params = self.schemas.validate(
                    method,
                    ApiParams(body=body_params, query=query_params, uri=uri_params),
                )
            except APIAbort as e:
                self.logger.exception("{} {}", api_name, e)
                abort(e.http_status, message=str(e))
            except Exception as e:
                self.logger.exception("{} API error: {}", api_name, e)
                abort(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
                )
        else:
            params = ApiParams(None, None, None)

        # Automatically authorize the operation only if the API schema for the
        # active HTTP method has authorization enabled, using the selected
        # parameters. Automatic authorization can be disabled by selecting
        # API_AUTHORIZATION.NONE for a particular method's schema where either
        # no authorization is required, or a specialized authorization
        # mechanism is required by the API.
        auth_params = self.schemas.authorize(method, params)
        if auth_params:
            self.logger.info(
                "Authorizing with {}:{}, {}",
                auth_params.user,
                auth_params.access,
                auth_params.role,
            )
            try:
                self._check_authorization(
                    auth_params.user, auth_params.access, auth_params.role
                )
            except UnauthorizedAccess as e:
                self.logger.warning("{}: {}", api_name, e)
                abort(e.http_status, message=str(e))
            except Exception as e:
                self.logger.exception("{}: {}", api_name, e)
                abort(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
                )

        try:
            return execute(params, request)
        except APIAbort as e:
            self.logger.exception("{} {}", api_name, e)
            abort(e.http_status, message=str(e))
        except Exception as e:
            self.logger.exception("{} API error: {}", api_name, e)
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                message=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            )

    def _get(self, args: ApiParams, request: Request) -> Response:
        """
        ABSTRACT METHOD: override in subclass to perform operation

        Perform the requested GET operation, and handle any exceptions.

        Args:
            args: Type-normalized client argument sets
            request: Original incoming Request object

        Returns:
            Response to return to client
        """
        raise NotImplementedError(
            f"Class {self.__class__.__name__} doesn't override abstract _get method"
        )

    def _post(self, args: ApiParams, request: Request) -> Response:
        """
        ABSTRACT METHOD: override in subclass to perform operation

        Perform the requested POST operation, and handle any exceptions.

        Args:
            args: Type-normalized client argument sets
            request: Original incoming Request object

        Returns:
            Response to return to client
        """
        raise NotImplementedError(
            f"Class {self.__class__.__name__} doesn't override abstract _post method"
        )

    def _put(self, args: ApiParams, request: Request) -> Response:
        """
        ABSTRACT METHOD: override in subclass to perform operation

        Perform the requested PUT operation, and handle any exceptions.

        Args:
            args: Type-normalized client argument sets
            request: Original incoming Request object

        Returns:
            Response to return to client
        """
        raise NotImplementedError(
            f"Class {self.__class__.__name__} doesn't override abstract _put method"
        )

    def _delete(self, args: ApiParams, request: Request) -> Response:
        """
        ABSTRACT METHOD: override in subclass to perform operation

        Perform the requested DELETE operation, and handle any exceptions.

        Args:
            args: Type-normalized client argument sets
            request: Original incoming Request object

        Returns:
            Response to return to client
        """
        raise NotImplementedError(
            f"Class {self.__class__.__name__} doesn't override abstract _delete method"
        )

    @Auth.token_auth.login_required(optional=True)
    def get(self, **kwargs):
        """
        Handle an authenticated GET operation on the Resource
        """
        return self._dispatch(API_METHOD.GET, request, kwargs)

    @Auth.token_auth.login_required(optional=True)
    def post(self, **kwargs):
        """
        Handle an authenticated POST operation on the Resource
        """
        return self._dispatch(API_METHOD.POST, request, kwargs)

    @Auth.token_auth.login_required(optional=True)
    def put(self, **kwargs):
        """
        Handle an authenticated PUT operation on the Resource
        """
        return self._dispatch(API_METHOD.PUT, request, kwargs)

    @Auth.token_auth.login_required(optional=True)
    def delete(self, **kwargs):
        """
        Handle an authenticated DELETE operation on the Resource
        """
        return self._dispatch(API_METHOD.DELETE, request, kwargs)
