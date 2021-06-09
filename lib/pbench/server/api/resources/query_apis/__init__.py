import json

from datetime import datetime
from enum import Enum
from http import HTTPStatus
from logging import Logger
from typing import Any, AnyStr, Callable, Dict, List, Union
from urllib.parse import urljoin

import requests
from dateutil import parser as date_parser
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from flask import request
from flask_restful import Resource, abort

from pbench.server import PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.database.models.template import Template
from pbench.server.database.models.tracker import Dataset
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

    Raises:
        ConversionError: input can't be converted

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

    Raises:
        ConversionError: input can't be converted

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

    Raises:
        ConversionError: input can't be converted

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

    Raises:
        ConversionError: input can't be converted

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

    Raises:
        ConversionError: input can't be converted

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

    def __str__(self) -> str:
        return (
            f"Parameter<{self.name}:{self.type}"
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
            processed[p] = tp.type.convert(json_data[p]) if tp else json_data[p]
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
    """

    CREATE = 1
    READ = 2
    UPDATE = 3
    DELETE = 4


class ElasticBase(Resource):
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
        *,
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
        self.prefix = config.get("Indexing", "index_prefix")
        host = config.get("elasticsearch", "host")
        port = config.get("elasticsearch", "port")
        self.es_url = f"http://{host}:{port}"
        self.schema = schema
        self.role = role

    def _get_user_term(self, json: JSON) -> Dict[str, str]:
        """
        Generate the user term for an Elasticsearch document query. If the
        specified "user" parameter is not None, search for documents with that
        value as the authorized owner. If the "user" parameter is absent or
        None, and the "access" parameter is "public", search for all published
        documents.

        TODO: Currently this code supports either all published data, or all
        data owned by a specified user. More work in query construction must
        be completed to support additional combinations. I plan to support
        additional flexibility in a separate PR based on issue #2370.

        Args:
            JSON query parameters containing keys:
                "user": Pbench internal username if present and not None
                "access": Access category, "public" or "private"; defaults
                    to "private" if "user" is specified, and "public" if
                    user is not specified. (NOTE: other combinations are
                    not currently supported.)

        Raises:
            UnsupportedAccessMode: This is a temporary situation due to the
            current query limitations. When the full semantics are complete
            there will be no "illegal" constraint combinations but only
            combinations that yield no data (e.g, "private" data for another
            user).

        Returns:
            An assembled Elasticsearch query term
        """
        user = json.get("user")
        if user:
            term = {"authorization.owner": user}
        elif json.get("access") == Dataset.PRIVATE_ACCESS:
            raise UnsupportedAccessMode(user, Dataset.PRIVATE_ACCESS)
        else:
            term = {"authorization.access": Dataset.PUBLIC_ACCESS}
        return term

    def _gen_month_range(self, index: str, start: datetime, end: datetime) -> str:
        """
        Construct a comma-separated list of index names qualified by year and
        month suitable for use in the Elasticsearch /_search query URI.

        The month is incremented by 1 from "start" to "end"; for example,
        _gen_month_range('run', '2020-08', '2020-10') might result
        in

            'drb.v4.run.2020-08,drb.v4.run.2020-09,drb.v4.run.2020-10,'

        Args:
            index: The desired monthly index root (e.g., 'run')
            start: The start time
            end: The end time

        Returns:
            A comma-separated list of month-qualified index names
        """
        template = Template.find(index)
        indices = ""
        first_month = start.replace(day=1)
        last_month = end + relativedelta(day=31)
        for m in rrule.rrule(rrule.MONTHLY, dtstart=first_month, until=last_month):
            indices += (
                template.index_template.format(
                    prefix=self.prefix,
                    version=template.version,
                    idxname=template.idxname,
                    year=f"{m.year:04}",
                    month=f"{m.month:02}",
                    day="*",
                )
                + ","
            )
        return indices

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Given the client Request payload, perform any preprocessing activities
        necessary prior to constructing an Elasticsearch query.

        The base class assumes no preprocessing is necessary, and returns an
        empty dictionary to indicate that the Elasticsearch operation should
        continue; this can be overridden by subclasses as necessary.

        The value returned here (if not None) will be passed to the "assemble"
        and "postprocess" methods to provide shared context across the set of
        operations. Note that "assemble" can modify the CONTEXT dict to pass
        additional context to "postprocess" if necessary.

        Args:
            client_json: Request JSON payload

        Raises:
            Any errors in the postprocess method shall be reported by
            exceptions which will be logged and will terminate the operation.

        Returns:
            None if Elasticsearch query shouldn't proceed, or a CONTEXT dict to
            provide shared context for the assemble and postprocess methods.
        """
        return {}

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Assemble the Elasticsearch parameters.

        This is an abstract method that must be implemented by a subclass.

        Args:
            json_data: Input JSON payload, processed by type conversion
            context: CONTEXT dict returned by preprocess method

        Raises:
            Any errors in the assemble method shall be reported by exceptions
            which will be logged and will terminate the operation.

        Returns:
            A dict describing the URI path, the json body, and query parameters
            to pass to Elasticsearch:
                path: The path part of the Elasticsearch URI
                kwargs: A kwargs dict for the requests API; e.g.,
                    json: The JSON query to pass to Elasticsearch
                    params: Query parameters to pass to Elasticsearch
                    headers: Request headers
        """
        raise NotImplementedError()

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        """
        Given the Elasticsearch Response object, construct a JSON document to
        be returned to the original caller.

        This is an abstract method that must be implemented by a subclass.

        Args:
            es_json: Elasticsearch Response payload
            context: CONTEXT value returned by preprocess method

        Raises:
            Any errors in the postprocess method shall be reported by
            exceptions which will be logged and will terminate the operation.

        Returns:
            The JSON payload to be returned to the caller
        """
        raise NotImplementedError()

    def _call(self, method: Callable, json_data: JSON):
        """
        Perform the requested call to Elasticsearch, and handle any exceptions.

        Args:
            method: Any requests HTTP method (e.g., requests.post)
            json_data: Type-normalized client JSON input

        Returns:
            Postprocessed JSON body to return to client
        """
        klasname = self.__class__.__name__
        try:
            context = self.preprocess(json_data)
            self.logger.debug("PREPROCESS returns {}", context)
            if context is None:
                return "", HTTPStatus.NO_CONTENT
        except UnauthorizedAccess as e:
            self.logger.warning("{}", e)
            abort(HTTPStatus.FORBIDDEN, message="Not Authorized")
        except KeyError as e:
            self.logger.exception("{} problem in preprocess, missing {}", klasname, e)
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        except Exception as e:
            self.logger.exception("{} preprocess failed: {}", klasname, e)
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        try:
            # prepare payload for Elasticsearch query
            es_request = self.assemble(json_data, context)
            path = es_request.get("path")
            url = urljoin(self.es_url, path)
            self.logger.debug("ASSEMBLE returned URL {}", url)
        except Exception as e:
            self.logger.exception("{} assembly failed: {}", klasname, e)
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        try:
            # perform the Elasticsearch query
            es_response = method(url, **es_request["kwargs"])
            self.logger.debug(
                "ES query response {}:{}", es_response.reason, es_response.status_code
            )
            es_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.logger.exception(
                "{} HTTP error {} from Elasticsearch request: {}",
                klasname,
                e,
                es_request,
            )
            abort(
                HTTPStatus.BAD_GATEWAY,
                message=f"Elasticsearch query failure {e.response.reason} ({e.response.status_code})",
            )
        except requests.exceptions.ConnectionError:
            self.logger.exception(
                "{}: connection refused during the Elasticsearch request", klasname
            )
            abort(
                HTTPStatus.BAD_GATEWAY,
                message="Network problem, could not reach Elasticsearch",
            )
        except requests.exceptions.Timeout:
            self.logger.exception(
                "{}: connection timed out during the Elasticsearch request", klasname
            )
            abort(
                HTTPStatus.GATEWAY_TIMEOUT,
                message="Connection timed out, could reach Elasticsearch",
            )
        except requests.exceptions.InvalidURL:
            self.logger.exception(
                "{}: invalid url {} during the Elasticsearch request", klasname, url
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        except Exception as e:
            self.logger.exception(
                "{}: exception {} occurred during the Elasticsearch request",
                klasname,
                type(e).__name__,
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        try:
            # postprocess Elasticsearch response
            return self.postprocess(es_response.json(), context)
        except PostprocessError as e:
            msg = f"{klasname}: the query postprocessor was unable to complete: {e}"
            self.logger.warning("{}", msg)
            abort(e.status, message=msg, data=e.data)
        except KeyError as e:
            self.logger.error("{}: missing Elasticsearch key {}", klasname, e)
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                message=f"Missing Elasticsearch key {e}",
            )
        except Exception as e:
            self.logger.exception(
                "{}: unexpected problem postprocessing Elasticsearch response {}: {}",
                klasname,
                es_response.json(),
                e,
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

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
        json_data = request.get_json(silent=True)
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
                HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR IN VALIDATION"
            )

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
        return self._call(requests.post, new_data)

    @Auth.token_auth.login_required(optional=True)
    def get(self):
        """
        Handle a GET operation involving a call to the server's Elasticsearch
        instance. The post-processing of the Elasticsearch query is handled
        the subclasses through their postprocess() methods.
        """
        return self._call(requests.get, None)
