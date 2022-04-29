from datetime import datetime
from enum import Enum
from http import HTTPStatus
import json
from json.decoder import JSONDecodeError
from logging import Logger
from typing import Any, Callable, List, Union

from dateutil import parser as date_parser
from flask import request
from flask.wrappers import Request, Response
from flask_restful import Resource, abort
from sqlalchemy.orm.query import Query

from pbench.server import JSON, JSONOBJECT, JSONVALUE, PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    MetadataBadKey,
    MetadataNotFound,
)
from pbench.server.database.models.users import User


class UnauthorizedAccess(Exception):
    """
    The user is not authorized for the requested operation on the specified
    resource.
    """

    def __init__(
        self,
        user: Union[User, None],
        operation: "API_OPERATION",
        owner: str,
        access: str,
        http_status: int = HTTPStatus.FORBIDDEN,
    ):
        self.user = user
        self.operation = operation
        self.owner = owner
        self.access = access
        self.http_status = http_status

    def __str__(self) -> str:
        return f"{'User ' + self.user.username if self.user else 'Unauthenticated client'} is not authorized to {self.operation.name} a resource owned by {self.owner} with {self.access} access"


class SchemaError(TypeError):
    """
    Generic base class for errors in processing a JSON schema.
    """

    def __init__(self, http_status: int = HTTPStatus.BAD_REQUEST):
        self.http_status = http_status

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


def convert_json(value: JSONOBJECT, parameter: "Parameter") -> JSONOBJECT:
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
    DATE = ("Date", convert_date)
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
        uri_parameter: bool = False,
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
            uri_parameter: whether the parameter is coming from the uri
            string_list: if a delimiter is specified, individual string values
                will be split into lists.
        """
        self.name = name
        self.type = type
        self.keywords = [k.lower() for k in keywords] if keywords else None
        self.element_type = element_type
        self.required = required
        self.uri_parameter = uri_parameter
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

    # We treat some Dataset object attributes as user-accessible metadata for
    # the purposes of these APIs even though they're represented as columns on
    # the main SQL table.
    METADATA = sorted(
        Metadata.USER_METADATA
        + [Dataset.ACCESS, Dataset.CREATED, Dataset.OWNER, Dataset.UPLOADED]
    )

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

    def _validate_query_params(self, request: Request, schema: Schema) -> JSONOBJECT:
        """
        When an API accepts HTTP query parameters from the URL, these aren't
        automatically validated by the dispatcher. This method collects query
        parameters into a JSON object and validates them against a specified
        schema.

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

        # Normalize and validate the keys we got via the HTTP query string.
        # These aren't automatically validated by the superclass, so we
        # have to do it here.
        return schema.validate(json)

    def _check_authorization(self, user: Union[str, None], access: Union[str, None]):
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

        for API_OPERATION.UPDATE:

            An authenticated user is required.

            Any authenticated user can update their own data.

            Any authenticated ADMIN user can update any data.

        Args:
            user: The username parameter to the API, or None
            access: The access parameter to the API, or None

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
        self.logger.debug(
            "Authorizing {} access for {} to user {} with access {}",
            self.role,
            authorized_user,
            user,
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
        if self.role == API_OPERATION.READ and access == Dataset.PUBLIC_ACCESS:
            # We are reading public data: this is always allowed.
            pass
        else:
            # ROLE is UPDATE, CREATE, DELETE or ACCESS is private; we need to
            # evaluate access rights to determine whether to allow the request
            if authorized_user is None:
                # An unauthenticated user is never allowed to access private
                # data nor to perform an potential mutation of data: REJECT
                self.logger.warning(
                    "Attempt to {} user {} data without login", self.role, user
                )
                raise UnauthorizedAccess(
                    authorized_user, self.role, user, access, HTTPStatus.UNAUTHORIZED
                )
            elif self.role != API_OPERATION.READ and user is None:
                # No target user is specified, so we won't allow mutation of
                # data: REJECT
                self.logger.warning(
                    "Unauthorized attempt by {} to {} data with defaulted user",
                    authorized_user,
                    self.role,
                )
                raise UnauthorizedAccess(
                    authorized_user, self.role, user, access, HTTPStatus.FORBIDDEN
                )
            elif (
                user
                and user != authorized_user.username
                and not authorized_user.is_admin()
            ):
                # We are mutating data, or reading private data, so the
                # authenticated user must either be the owner of the data or
                # must have ADMIN role: REJECT
                self.logger.warning(
                    "Unauthorized attempt by {} to {} user {} data",
                    authorized_user,
                    self.role,
                    user,
                )
                raise UnauthorizedAccess(
                    authorized_user, self.role, user, access, HTTPStatus.FORBIDDEN
                )
            else:
                # We have determined that there is an authenticated user with
                # legitimate access: the data is public and the operation is
                # READ, the user owns the data, or the user has ADMIN role.
                pass

    def _build_sql_query(self, parameters: JSON, base_query: Query) -> Query:
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
            JSON query parameters containing keys:
                "owner": Pbench username to restrict search to datasets owned by
                    a specific user.
                "access": Access category, "public" or "private" to restrict
                    search to datasets with a specific access category.
            base_query: A SQLAlchemy Query object to be extended with user and
                access terms as appropriate

        Returns:
            An SQLAlchemy Query object that may include additional query terms
        """
        user = parameters.get("owner")
        access = parameters.get("access")
        authorized_user: User = Auth.token_auth.current_user()
        authorized_id = str(authorized_user.id) if authorized_user else None
        is_admin = authorized_user.is_admin() if authorized_user else False
        query = base_query

        self.logger.debug(
            "QUERY auth ID {}, user {!r}, access {!r}, admin {}",
            authorized_id,
            user,
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
        if not authorized_user or (user and user != authorized_id and not is_admin):
            query = query.filter(Dataset.access == Dataset.PUBLIC_ACCESS)
            self.logger.debug("QUERY: not self public")
        elif access:
            query = query.filter(Dataset.access == access)
            if not user and access == Dataset.PRIVATE_ACCESS and not is_admin:
                query = query.filter(Dataset.owner_id == authorized_id)
                user_term = True
            self.logger.debug("QUERY: user: {}, access: {}", authorized_id, access)
        elif not user and not is_admin:
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
                "QUERY: default, user: {}", user if user else authorized_user
            )

        # If a user is specified, and we haven't already added a user term, add
        # it now.
        if user and not user_term:
            query = query.filter(Dataset.owner_id == user)

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
            if i == Dataset.ACCESS:
                metadata[i] = dataset.access
            elif i == Dataset.CREATED:
                metadata[i] = f"{dataset.created:%Y-%m-%d:%H:%M}"
            elif i == Dataset.OWNER:
                metadata[i] = dataset.owner.username
            elif i == Dataset.UPLOADED:
                metadata[i] = f"{dataset.uploaded:%Y-%m-%d:%H:%M}"
            elif Metadata.is_key_path(i, Metadata.USER_METADATA):
                try:
                    metadata[i] = Metadata.getvalue(dataset=dataset, key=i)
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
        self, method: Callable, request: Request, uri_parameters: JSON = {}
    ) -> Response:
        """
        This is a common front end for HTTP operations.

        If the class has a parameter schema, and the HTTP operation is not GET
        (which doesn't accept a request payload), we'll validate and normalize
        the request payload here before calling the subclass helper method.

        Args:
            method: A reference to the implementation method
            request: The flask Request object containing payload and headers
            uri_parameters: URI encoded keyword-arg supplied by the Flask
            framework

        Returns:
            Flask Response object generally constructed implicitly from a JSON
            payload and HTTP status.
        """

        api_name = self.__class__.__name__

        # We don't accept or process a request payload for GET, or if no
        # parameter schema is defined
        if not self.schema or method == self._get:
            try:
                return method(uri_parameters, request)
            except SchemaError as e:
                self.logger.exception("{}: SchemaError {}", api_name, e)
                abort(e.http_status, message=str(e))

        try:
            json_data = request.get_json()
        except Exception as e:
            self.logger.warning(
                "{}: Bad JSON in request, {!r}, {!r}",
                api_name,
                str(e),
                request.data,
            )
            abort(HTTPStatus.BAD_REQUEST, message="Invalid request payload")

        try:
            if json_data:
                json_data.update(uri_parameters)
            else:
                json_data = uri_parameters
            new_data = self.schema.validate(json_data)
        except UnverifiedUser as e:
            self.logger.warning("{}: {}", api_name, str(e))
            abort(e.http_status, message=str(e))
        except SchemaError as e:
            self.logger.warning("{}: {} on {!r}", api_name, str(e), json_data)
            abort(e.http_status, message=str(e))
        except Exception as e:
            self.logger.exception(
                "{}: unexpected validation exception in {}: {}",
                api_name,
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
                self.logger.warning("{}: {}", api_name, e)
                abort(e.http_status, message=str(e))

        try:
            return method(new_data, request)
        except SchemaError as e:
            self.logger.exception("{}: SchemaError {}", api_name, e)
            abort(e.http_status, message=str(e))

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
    def get(self, **kwargs):
        """
        Handle an authenticated GET operation on the Resource
        """
        return self._dispatch(self._get, request, kwargs)

    @Auth.token_auth.login_required(optional=True)
    def post(self, **kwargs):
        """
        Handle an authenticated POST operation on the Resource
        """
        return self._dispatch(self._post, request, kwargs)

    @Auth.token_auth.login_required(optional=True)
    def put(self, **kwargs):
        """
        Handle an authenticated PUT operation on the Resource
        """
        return self._dispatch(self._put, request, kwargs)

    @Auth.token_auth.login_required(optional=True)
    def delete(self, **kwargs):
        """
        Handle an authenticated DELETE operation on the Resource
        """
        return self._dispatch(self._delete, request, kwargs)
