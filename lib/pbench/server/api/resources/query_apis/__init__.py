from datetime import datetime
from enum import Enum
from logging import Logger
from typing import Any, AnyStr, Callable, Dict, List
from urllib.parse import urljoin

import requests
from dateutil import parser as date_parser
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from flask import request
from flask_restful import Resource, abort

from pbench.server import PbenchServerConfig
from pbench.server.api.auth import Auth


class SchemaError(TypeError):
    """
    Generic base class for errors in processing a JSON schema.
    """

    pass


class InvalidRequestPayload(SchemaError):
    """
    A required client JSON input document is missing.
    """

    def __str__(self):
        return "Invalid request payload"


class MissingParameters(SchemaError):
    """
    One or more required JSON keys are missing, or the values are unexpectedly
    empty.
    """

    def __init__(self, keys: List[AnyStr]):
        self.keys = keys

    def __str__(self):
        return f"Missing required parameters: {','.join(self.keys)}"


class ConversionError(SchemaError):
    """
    ConversionError Used to report an invalid parameter type
    """

    def __init__(self, value: Any, expected_type: str, actual_type: str):
        """
        __init__ Construct a ConversionError exception

        Args:
            value: The value we tried to convert
            expected_type: The expected type
            actual_type: The actual type
        """
        self.value = value
        self.expected_type = expected_type
        self.actual_type = actual_type

    def __str__(self):
        return f"Value {self.value!r} ({self.actual_type}) cannot be parsed as a {self.expected_type}"


def convert_date(value: str) -> datetime:
    """
    convert_date Convert a date/time string to a datetime.datetime object.

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
    convert_username Convert the external representation of a username
    by validating that the specified username exists, and returns the
    desired internal representation of that user.

    TODO: when we get our user model straightened out, this will
    convert the external user representation (either username or email
    address) to whatever internal representation we want to store in
    the Elasticsearch database, whether that's a SQL row ID or something
    else. For now, it just validates that the username string is a real
    user.

    Args:
        value: external user representation

    Raises:
        ConversionError: input can't be converted

    Returns:
        internal username representation
    """
    try:
        return Auth.validate_user(value)
    except Exception:
        raise ConversionError(value, "username", type(value).__name__)


def convert_json(value: dict) -> dict:
    """
    convert_json Process a parameter of JSON type; currently just by validating
    that it's a Python dict.

    Args:
        value: JSON dict

    Raises:
        ConversionError: input can't be converted

    Returns:
        The JSON dict
    """
    if type(value) is not dict:
        raise ConversionError(value, dict.__name__, type(value).__name__)
    return value


def convert_string(value: str) -> str:
    """
    convert_string Verify that the parameter value is a string (e.g.,
    not a JSON dict, or an int), and return it.

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

    def __init__(self, name: AnyStr, convert: Callable[[AnyStr], Any]):
        """
        ParamType Enum initializer: this uses a mixed-case name string in
        addition to the conversion method simply because with only the
        Callable value I ran into naming issues.
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

    def __init__(self, name: AnyStr, type: ParamType, required: bool = False):
        """
        __init__ Initialize a Parameter object describing a JSON parameter
        with its type and attributes.

        Args:
            name: Parameter name
            type: Parameter type
            required: whether the parameter is required (default to False)
        """
        self.name = name
        self.type = type
        self.required = required

    def invalid(self, json: Dict[AnyStr, Any]) -> bool:
        """
        Check whether the value of this parameter in the JSON document
        is invalid.

        If the parameter is required and missing (or null), then it's invalid;
        if the parameter is not required and specified as null, it's invalid.

        Args:
            json: The client JSON document being validated.

        Returns:
            True if unacceptable
        """
        return not json[self.name] if self.name in json else self.required

    def __str__(self) -> str:
        return f"Parameter<{self.name}:{self.type}>"


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
        __init__ Specify an interface schema as a list of Parameter objects.

        Args:
            parameters: a list of Parameter objects
        """
        self.parameters = {p.name: p for p in parameters}

    def validate(self, json_data: Dict[AnyStr, Any]) -> Dict[AnyStr, Any]:
        """
        validate Validate an incoming JSON document against the schema and
        return a new JSON dict with translated values.

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

    def __str__(self) -> str:
        return f"Schema<{self.parameters}>"


class ElasticBase(Resource):
    """
    ElasticBase A base class for Elasticsearch queries that allows subclasses
    to provide customers pre- and post- processing.

    This class extends the Flask Resource class in order to connect the post
    and get methods to Flask's URI routing algorithms. It implements a common
    JSON client payload intake and validation, along with the mechanism for
    calling Elasticsearch and processing errors.

    Hooks are defined for subclasses extending this class to "assemble" the
    Elasticsearch request payload from Pbench server data and the client's
    JSON payload, and to "postprocess" a successful response payload from
    Elasticsearch.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger, schema: Schema):
        """
        __init__ Construct the base class

        Args:
            config: server configuration
            logger: logger object
            schema: API schema: for example,
                    Schema(
                        Parameter("user", ParamType.USER, required=True),
                        Parameter("start", ParamType.DATE)
                    )

        NOTE: each class currently only supports one HTTP method, so we can
        describe only one set of parameters. If we ever need to change this,
        we can add a level and describe parameters by method.
        """
        super().__init__()
        self.logger = logger
        self.prefix = config.get("Indexing", "index_prefix")
        host = config.get("elasticsearch", "host")
        port = config.get("elasticsearch", "port")
        self.es_url = f"http://{host}:{port}"
        self.schema = schema

    def _get_user_term(self, user: str) -> dict:
        """
        _get_user_term Generate the user term for an Elasticsearch document
        query. If the specified user parameter is not None, search for
        documents with that value as the authorized owner. If the user
        parameter is None, instead search for documents with public access.

        Args:
            user: Pbench internal username or None

        Returns:
            An assembled Elasticsearch query term
        """
        if user:
            term = {"authorization.owner": user}
        else:
            term = {"authorization.access": "public"}
        return term

    def _gen_month_range(self, index: str, start: datetime, end: datetime) -> str:
        """
        _gen_month_range Construct a comma-separated list of index names
        qualified by year and month suitable for use in the Elasticsearch
        /_search query URI.

        The month is incremented by 1 from "start" to "end"; for example,
        _gen_month_range('v4.run.', '2020-08', '2020-10') will result
        in

            'drb.v4.run.2020-08,drb.v4.run.2020-09,drb.v4.run.2020-10,'

        Args:
            index: The desired monthly index root
            start: The start time
            end: The end time

        Returns:
            A comma-separated list of month-qualified index names
        """
        monthResults = list()
        queryString = ""
        first_month = start.replace(day=1)
        last_month = end + relativedelta(day=31)
        for m in rrule.rrule(rrule.MONTHLY, dtstart=first_month, until=last_month):
            monthResults.append(m.strftime("%Y-%m"))

        # TODO: hardcoding the index here is risky. We need a framework to
        # help the web services understand index versions and template
        # formats, probably by building a persistent database from the
        # index template documents at startup. This is TBD.
        for monthValue in monthResults:
            if index == "v4.result-data.":
                queryString += f"{self.prefix + index + monthValue}-*,"
            else:
                queryString += f"{self.prefix + index + monthValue},"
        return queryString

    def assemble(self, json_data: Dict[AnyStr, Any]) -> Dict[AnyStr, Any]:
        """
        assemble Assemble the Elasticsearch parameters

        This must be overridden by the subclasses!

        Args:
            json_data: Input JSON payload, processed by type conversion

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

    def postprocess(self, es_json: Dict[AnyStr, Any]) -> Dict[AnyStr, Any]:
        """
        postprocess Given the Elasticsearch Response object, construct a JSON
                dict to be returned to the original caller.

        This must be overridden by the subclasses!

        Args:
            response: Response object

        Raises:
            Any errors in the postprocess method shall be reported by
            exceptions which will be logged and will terminate the operation.

        Returns:
            The JSON payload to be returned to the caller
        """
        raise NotImplementedError()

    def _call(self, method: Callable, json_data: Dict[AnyStr, Any]):
        """
        _call Perform the requested call to Elasticsearch, and handle any
        exceptions.

        Args:
            method: Any requests HTTP method (e.g., requests.post)
            json_data: Type-normalized client JSON input

        Returns:
            Postprocessed JSON body to return to client
        """
        try:
            es_request = self.assemble(json_data)
            path = es_request.get("path")
            url = urljoin(self.es_url, path)
        except Exception as e:
            self.logger.exception("Blew it in setup: {}", type(e).__name__)
            abort(500, message="INTERNAL ERROR")

        try:
            # query Elasticsearch
            es_response = method(url, **es_request["kwargs"])
            es_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.logger.exception("HTTP error {} from Elasticsearch request", e)
            abort(
                502,
                message="Elasticsearch query failure {e.response.reason} ({e.response.status_code})",
            )
        except requests.exceptions.ConnectionError:
            self.logger.exception("Connection refused during the Elasticsearch request")
            abort(502, message="Network problem, could not reach Elasticsearch")
        except requests.exceptions.Timeout:
            self.logger.exception(
                "Connection timed out during the Elasticsearch request"
            )
            abort(504, message="Connection timed out, could reach Elasticsearch")
        except requests.exceptions.InvalidURL:
            self.logger.exception(
                "Invalid url {} during the Elasticsearch request", url
            )
            abort(500, message="INTERNAL ERROR")
        except Exception as e:
            self.logger.exception(
                "Exception {} occurred during the Elasticsearch request",
                type(e).__name__,
            )
            abort(500, message="INTERNAL ERROR")

        try:
            return self.postprocess(es_response.json())
        except Exception as e:
            self.logger.exception(
                "Unexpected problem postprocessing Elasticsearch response {}: {}",
                es_response.json(),
                e,
            )
            abort(500, message="INTERNAL ERROR")

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
        """
        json_data = request.get_json(silent=True)
        try:
            new_data = self.schema.validate(json_data)
        except SchemaError as e:
            # The format string here is important as the value we're
            # trying to convert might contain "{}" brackets that would
            # be interpreted as formatting commands.
            self.logger.warning("{}", str(e))
            abort(400, message=str(e))
        return self._call(requests.post, new_data)

    def get(self):
        """
        Handle a GET operation involving a call to the server's Elasticsearch
        instance. The post-processing of the Elasticsearch query is handled
        the subclasses through their postprocess() methods.
        """
        return self._call(requests.get, None)
