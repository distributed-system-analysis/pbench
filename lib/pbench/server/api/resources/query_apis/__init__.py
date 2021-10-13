from datetime import datetime
from http import HTTPStatus
from logging import Logger
from typing import Any, Callable, Dict, Iterator
from urllib.parse import urljoin

from dateutil import rrule
from dateutil.relativedelta import relativedelta
import elasticsearch
from flask.wrappers import Response
from flask_restful import abort
import requests

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    API_OPERATION,
    ApiBase,
    JSON,
    PostprocessError,
    Schema,
    UnauthorizedAccess,
    UnsupportedAccessMode,
)
from pbench.server.database.models.template import Template
from pbench.server.database.models.datasets import Dataset, DatasetNotFound
from pbench.server.database.models.users import User

# A type defined to allow the preprocess subclass method to provide shared
# context with the assemble and postprocess methods.
CONTEXT = Dict[str, Any]


class ElasticBase(ApiBase):
    """
    A base class for Elasticsearch queries that allows subclasses to provide
    custom pre- and post- processing.

    This class extends the ApiBase class in order to connect the post
    and get methods to Flask's URI routing algorithms. It implements a common
    mechanism for calling Elasticsearch and processing errors.

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
        super().__init__(config, logger, schema, role=role)
        self.prefix = config.get("Indexing", "index_prefix")
        host = config.get("elasticsearch", "host")
        port = config.get("elasticsearch", "port")
        self.es_url = f"http://{host}:{port}"

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

    def _post(self, json_data: JSON, _) -> Response:
        """
        Handle a Pbench server POST operation that will involve a call to the
        server's configured Elasticsearch instance. The assembly and
        post-processing of the Elasticsearch query are handled by the
        subclasses through the assemble() and postprocess() methods;
        we rely on the ApiBase superclass to provide basic JSON parameter
        validation and normalization.
        """
        return self._call(requests.post, json_data)

    def _get(self, json_data: JSON, _) -> Response:
        """
        Handle a GET operation involving a call to the server's Elasticsearch
        instance. The post-processing of the Elasticsearch query is handled
        the subclasses through their postprocess() methods.
        """
        return self._call(requests.get, None)


class ElasticBulkBase(ApiBase):
    """
    A base class for bulk Elasticsearch queries that allows subclasses to
    provide a generator to produce bulk command documents with common setup and
    results processing.

    This class extends the ApiBase class in order to connect the post
    and get methods to Flask's URI routing algorithms. It implements a common
    mechanism for calling the Elasticsearch package streaming_bulk helper, and
    processing the response documents.
    """

    def __init__(
        self,
        config: PbenchServerConfig,
        logger: Logger,
        schema: Schema,
        *,  # following parameters are keyword-only
        role: API_OPERATION = API_OPERATION.UPDATE,
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
        """
        super().__init__(config, logger, schema, role=role)
        host = config.get("elasticsearch", "host")
        port = config.get("elasticsearch", "port")
        self.es_url = f"http://{host}:{port}"

    def generate_documents(self, json_data: JSON, dataset: Dataset) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk commands to be fed to the
        streaming_bulk helper.

        This is an abstract method that must be implemented by a subclass.

        Args:
            json_data: JSON dictionary of type-normalized key-value pairs
                controller: the controller that generated the dataset
                name: name of the dataset to publish
                access: The desired access level of the dataset

            dataset: The associated Dataset object
        """
        raise NotImplementedError()

    def complete(self, dataset: Dataset, json_data: JSON, error_count: int) -> None:
        """
        Complete a bulk Elasticsearch operation, generally by modifying the
        source Dataset resource.

        This is an abstract method that must be implemented by a subclass.

        Args:

            dataset: The associated Dataset object

            json_data: JSON dictionary of type-normalized key-value pairs
                controller: the controller that generated the dataset
                name: name of the dataset to publish
                access: The desired access level of the dataset

            error_count: The number of errors encountered during the bulk
                operation. We want to support idempotency: the Dataset should
                not be altered unless the error_count is 0.
        """
        raise NotImplementedError()

    def _post(self, json_data: JSON, _) -> Response:
        """
        Perform the requested POST operation, and handle any exceptions.

        NOTE: This is called by the ApiBase post() method through its dispatch
        method, which provides parameter validation.

        Args:
            json_data: Type-normalized client JSON input
            _: Original incoming Request object (not used)

        Returns:
            Response to return to client
        """
        klasname = self.__class__.__name__

        try:
            dataset = Dataset.attach(
                controller=json_data["controller"], name=json_data["name"]
            )
        except DatasetNotFound as e:
            abort(HTTPStatus.NOT_FOUND, message=str(e))

        owner = User.query(id=dataset.owner_id)
        if not owner:
            self.logger.error(
                "Dataset owner ID {} cannot be found in Users", dataset.owner_id
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="Dataset owner not found")

        # For bulk Elasticsearch operations, we check authorization against the
        # ownership of a designated dataset rather than having an explicit
        # "user" JSON parameter. This will raise UnauthorizedAccess on failure.
        try:
            self._check_authorization(owner.username, json_data["access"])
        except UnauthorizedAccess as e:
            abort(HTTPStatus.FORBIDDEN, message=str(e))

        # Build an Elasticsearch instance to manage the bulk update
        elastic = elasticsearch.Elasticsearch([self.es_url])

        try:
            # Pass the bulk command generator to the helper
            results = elasticsearch.helpers.streaming_bulk(
                elastic,
                self.generate_documents(json_data, dataset),
                raise_on_exception=False,
                raise_on_error=False,
            )
        except Exception as e:
            self.logger.exception(
                "{}: exception {} occurred during the Elasticsearch request",
                klasname,
                type(e).__name__,
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        report = {}
        count = 0
        error_count = 0
        for ok, response in results:
            count += 1
            u = response["update"]
            status = "ok"
            if "error" in u:
                e = u["error"]
                status = e["type"]
                self.logger.debug(
                    "{} ({}: {}) for id {} in index {}",
                    u["status"],
                    status,
                    e["reason"],
                    u["_id"],
                    u["_index"],
                )
                error_count += 1
            cnt = report.get(status, 0)
            report[status] = cnt + 1

        self.logger.info(
            "Update access for dataset {}: {} successful document updates and {} failures",
            dataset,
            count - error_count,
            error_count,
        )

        # Let the subclass complete the operation
        self.complete(dataset, json_data, error_count)

        # Return the report document as the success response, or abort with an
        # internal error if we weren't 100% successful. Some elasticsearch
        # documents may have been affected, but the client will be able to try
        # again. TODO: switching to `pyesbulk` will automatically handle
        # retrying on non-terminal errors, but this requires some cleanup
        # work on the pyesbulk side.
        if error_count > 0:
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                message=f"{error_count:d} of {count:d} Elasticsearch document UPDATE operations failed",
                data=report,
            )

        return report
