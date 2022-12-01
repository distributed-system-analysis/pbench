from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
import json
from logging import Logger
import re
from typing import Any, Callable, Dict, Iterator, List, Optional
from urllib.parse import urljoin

from dateutil import rrule
from dateutil.relativedelta import relativedelta
from elasticsearch import Elasticsearch, helpers, VERSION
from flask import jsonify
from flask.wrappers import Response
import requests

from pbench.server import JSON, PbenchServerConfig
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    APIAbort,
    ApiBase,
    ApiParams,
    ApiSchema,
    ParamType,
    SchemaError,
    UnauthorizedAccess,
)
from pbench.server.auth.auth import Auth
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.template import Template
from pbench.server.database.models.users import User

# A type defined to allow the preprocess subclass method to provide shared
# context with the assemble and postprocess methods.
CONTEXT = Dict[str, Any]


class MissingBulkSchemaParameters(SchemaError):
    """
    The subclass schema is missing required schema elements to locate and
    authorize access to a dataset.
    """

    def __init__(self, subclass_name: str, message: str):
        super().__init__()
        self.subclass_name = subclass_name
        self.message = message

    def __str__(self) -> str:
        return f"API {self.subclass_name} is {self.message}"


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
        *schemas: ApiSchema,
    ):
        """
        Base class constructor.

        Args:
            config: server configuration
            logger: logger object
            schemas: List of API schemas: for example,
                ApiSchema(
                    ApiSchema.METHOD.GET,
                    ApiSchema.OPERATION.READ,
                    query_schema=Schema(Parameter("start", ParamType.DATE)),
                    uri_schema=Schema(Parameter("dataset", ParamType.DATASET))
                ),
                ApiSchema(
                    ApiSchema.METHOD.POST,
                    ApiSchema.OPERATION.UPDATE,
                    body_schema=Schema(Parameter("start", ParamType.DATE)),
                    uri_schema=Schema(Parameter("dataset", ParamType.DATASET))
                )
        """
        super().__init__(config, logger, *schemas)
        self.prefix = config.get("Indexing", "index_prefix")
        host = config.get("elasticsearch", "host")
        port = config.get("elasticsearch", "port")

        # TODO: For future flexibility, we should consider reading this entire
        # Elasticsearch URI from the config file as we do for the database
        # rather than stitching it together. This would allow backend control
        # over authentication and http vs https for example.
        self.es_url = f"http://{host}:{port}"

    def _build_elasticsearch_query(
        self, user: Optional[str], access: Optional[str], terms: List[JSON]
    ) -> JSON:
        """
        Generate the "query" parameter for an Elasticsearch _search request
        payload.

        NOTE: This method is not responsible for authorization checks; that's
        done by the `ApiBase._check_authorization()` method. This method is
        only concerned with generating a query to restrict the results to the
        set matching authorized user and access values. This method will build
        queries that do not reflect the input when given some inputs that must
        be prevented by authorization checks.

        Specifically, when asked for "access": "private" on behalf of an
        unauthenticated client or on behalf of an authenticated but non-admin
        client for a different user, the generated query will use "access":
        "public". These cases are designated below with "NOTE(UNAUTHORIZED)".

        Specific cases for user and access values:

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
            user: Pbench username to restrict search to datasets owned by
                a specific user.
            access: Access category, "public" or "private" to restrict
                search to datasets with a specific access category.
            terms: A list of JSON objects describing the Elasticsearch "terms"
                that must be matched for the query. (These are assumed to be
                AND clauses.)

        Returns:
            An assembled Elasticsearch "query" mode that includes the necessary
            user/access terms.
        """
        authorized_user: User = Auth.token_auth.current_user()
        authorized_id = str(authorized_user.id) if authorized_user else None
        is_admin = authorized_user.is_admin() if authorized_user else False

        filter = terms.copy()
        self.logger.debug(
            "QUERY auth ID {}, user {!r}, access {!r}, admin {}",
            authorized_id,
            user,
            access,
            is_admin,
        )

        combo_term = None
        access_term = None
        user_term = None

        # If a user is specified, assume we'll be selecting for that user
        if user:
            user_term = {"term": {"authorization.owner": user}}

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
            access_term = {"term": {"authorization.access": Dataset.PUBLIC_ACCESS}}
            self.logger.debug("QUERY: not self public: {}", access_term)
        elif access:
            access_term = {"term": {"authorization.access": access}}
            if not user and access == Dataset.PRIVATE_ACCESS and not is_admin:
                user_term = {"term": {"authorization.owner": authorized_id}}
            self.logger.debug("QUERY: user: {}, access: {}", user_term, access_term)
        elif not user and not is_admin:
            combo_term = {
                "dis_max": {
                    "queries": [
                        {"term": {"authorization.owner": authorized_id}},
                        {"term": {"authorization.access": Dataset.PUBLIC_ACCESS}},
                    ]
                }
            }
            self.logger.debug("QUERY: {{}} self + public: {}", combo_term)
        else:
            # Either "user" was specified and will be added to the filter,
            # or client is ADMIN and no access restrictions are required.
            self.logger.debug("QUERY: {{}} default, user: {}", user_term)

        # We control the order of terms here to allow stable unit testing.
        if combo_term:
            filter.append(combo_term)
        else:
            if access_term:
                filter.append(access_term)
            if user_term:
                filter.append(user_term)
        return {"bool": {"filter": filter}}

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

    def preprocess(self, params: ApiParams) -> CONTEXT:
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
            params: Type-normalized client parameters

        Raises:
            Any errors in the postprocess method shall be reported by
            exceptions which will be logged and will terminate the operation.

        Returns:
            None if Elasticsearch query shouldn't proceed, or a CONTEXT dict to
            provide shared context for the assemble and postprocess methods.
        """
        return {}

    def assemble(self, params: ApiParams, context: CONTEXT) -> JSON:
        """
        Assemble the Elasticsearch parameters.

        This is an abstract method that must be implemented by a subclass.

        Args:
            params: Type-normalized client parameters
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

    def _call(self, method: Callable, params: ApiParams):
        """
        Perform the requested call to Elasticsearch, and handle any exceptions.

        Args:
            method: requests package callable (e.g., requests.get)
            params: Type-normalized client parameters

        Returns:
            Postprocessed JSON body to return to client
        """
        klasname = self.__class__.__name__
        try:
            context = self.preprocess(params)
            self.logger.debug("PREPROCESS returns {}", context)
            if context is None:
                return "", HTTPStatus.NO_CONTENT
        except UnauthorizedAccess as e:
            self.logger.warning("{}", e)
            raise APIAbort(e.http_status, str(e))
        except KeyError as e:
            self.logger.exception("{} problem in preprocess, missing {}", klasname, e)
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
        try:
            # prepare payload for Elasticsearch query
            es_request = self.assemble(params, context)
            path = es_request.get("path")
            url = urljoin(self.es_url, path)
            self.logger.info(
                "ASSEMBLE returned URL {!r}, {!r}",
                url,
                es_request.get("kwargs").get("json"),
            )
        except Exception as e:
            self.logger.exception("{} assembly failed: {}", klasname, e)
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)

        try:
            # perform the Elasticsearch query
            es_response = method(url, **es_request["kwargs"])
            self.logger.debug(
                "ES query response {}:{}",
                es_response.reason,
                es_response.status_code,
            )
            es_response.raise_for_status()
            json_response = es_response.json()
        except requests.exceptions.HTTPError as e:
            self.logger.exception(
                "{} HTTP error {} from Elasticsearch request: {}",
                klasname,
                e,
                es_request,
            )
            raise APIAbort(
                HTTPStatus.BAD_GATEWAY,
                f"Elasticsearch query failure {e.response.reason} ({e.response.status_code})",
            )
        except requests.exceptions.ConnectionError:
            self.logger.exception(
                "{}: connection refused during the Elasticsearch request", klasname
            )
            raise APIAbort(
                HTTPStatus.BAD_GATEWAY, "Network problem, could not reach Elasticsearch"
            )
        except requests.exceptions.Timeout:
            self.logger.exception(
                "{}: connection timed out during the Elasticsearch request", klasname
            )
            raise APIAbort(
                HTTPStatus.GATEWAY_TIMEOUT,
                "Connection timed out, could reach Elasticsearch",
            )
        except requests.exceptions.InvalidURL:
            self.logger.exception(
                "{}: invalid url {} during the Elasticsearch request", klasname, url
            )
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
        except Exception as e:
            self.logger.exception(
                "{}: exception {} occurred during the Elasticsearch request",
                klasname,
                type(e).__name__,
            )
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)

        try:
            # postprocess Elasticsearch response
            return self.postprocess(json_response, context)
        except PostprocessError as e:
            msg = f"{klasname}: the query postprocessor was unable to complete: {e}"
            self.logger.warning("{}", msg)
            raise APIAbort(e.status, str(e.message))
        except KeyError as e:
            self.logger.error("{}: missing Elasticsearch key {}", klasname, e)
            raise APIAbort(
                HTTPStatus.INTERNAL_SERVER_ERROR, f"Missing Elasticsearch key {e}"
            )
        except Exception as e:
            self.logger.exception(
                "{}: unexpected problem postprocessing Elasticsearch response {}: {}",
                klasname,
                json_response,
                e,
            )
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)

    def _post(self, params: ApiParams, _) -> Response:
        """
        Handle a Pbench server POST operation that will involve a call to the
        server's configured Elasticsearch instance. The assembly and
        post-processing of the Elasticsearch query are handled by the
        subclasses through the assemble() and postprocess() methods;
        we rely on the ApiBase superclass to provide basic JSON parameter
        validation and normalization.
        """
        return self._call(requests.post, params)

    def _get(self, params: ApiParams, _) -> Response:
        """
        Handle a GET operation involving a call to the server's Elasticsearch
        instance. The post-processing of the Elasticsearch query is handled
        the subclasses through their postprocess() methods.
        """
        return self._call(requests.get, params)


@dataclass
class BulkResults:
    errors: int
    count: int
    report: defaultdict


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

    EXCEPTION_NAME = re.compile(r"^(\w+)")

    def __init__(
        self,
        config: PbenchServerConfig,
        logger: Logger,
        *schemas: ApiSchema,
        action: Optional[str] = None,
        require_stable: bool = False,
        require_map: bool = False,
    ):
        """
        Base class constructor.

        This method assumes and requires that a dataset will be located using
        the dataset name, so a ParamType.DATASET parameter must be defined
        in the subclass schema.

        Args:
            config: server configuration
            logger: logger object
            schemas: List of API schemas: for example,
                ApiSchema(
                    ApiSchema.METHOD.GET,
                    ApiSchema.OPERATION.READ,
                    query_schema=Schema(Parameter("start", ParamType.DATE)),
                    uri_schema=Schema(Parameter("dataset", ParamType.DATASET))
                ),
                ApiSchema(
                    ApiSchema.METHOD.POST,
                    ApiSchema.OPERATION.UPDATE,
                    body_schema=Schema(Parameter("start", ParamType.DATE)),
                    uri_schema=Schema(Parameter("dataset", ParamType.DATASET))
                )
            action: bulk Elasticsearch action (delete, create, update)
            require_stable: if True, fail if dataset state is mutating (-ing state)
            require_map: if True, fail if the dataset has no index map
        """
        super().__init__(config, logger, *schemas)
        host = config.get("elasticsearch", "host")
        port = config.get("elasticsearch", "port")

        api_name = self.__class__.__name__

        # TODO: For future flexibility, we should consider reading this entire
        # Elasticsearch URI from the config file as we do for the database
        # rather than stitching it together. This would allow backend control
        # over authentication and http vs https for example.
        self.elastic_uri = f"http://{host}:{port}"
        self.config = config
        self.action = action
        self.require_stable = require_stable
        self.require_map = require_map

        # Look for a parameter of type DATASET. It may be defined in any of the
        # three schemas (uri, query parameter, or request body), and we don't
        # care how it's named. That parameter must be required, since instances
        # of this base class operate on a specific dataset, and the schema
        # authorization mechanism must be set to use the DATASET.
        if not schemas:
            raise MissingBulkSchemaParameters(api_name, "no schema provided")
        dset = self.schemas.get_param_by_type(
            API_METHOD.POST,
            ParamType.DATASET,
            ApiParams(),
        )
        if not dset or not dset.parameter.required:
            raise MissingBulkSchemaParameters(
                api_name, "dataset parameter is not defined or not required"
            )
        if self.schemas[API_METHOD.POST].authorization != API_AUTHORIZATION.DATASET:
            raise MissingBulkSchemaParameters(
                api_name, "schema authorization is not by dataset"
            )

    def generate_actions(
        self, params: ApiParams, dataset: Dataset, map: dict[str, list[str]]
    ) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk operation actions driven by the
        dataset document map. For example:

        {
            "_op_type": "update",
            "_index": index_name,
            "_id": document_id,
            "doc": {"authorization": {"access": new_access}}
        }

        This is an abstract method that must be implemented by a subclass.

        Args:
            params: Type-normalized client parameters
            dataset: The associated Dataset object
            map: Elasticsearch index document map

        Returns:
            Sequence of Elasticsearch bulk action dict objects
        """
        raise NotImplementedError()

    def complete(self, dataset: Dataset, params: ApiParams, summary: JSON) -> None:
        """
        Complete a bulk Elasticsearch operation, perhaps by modifying the
        source Dataset resource.

        This is an abstract method that may be implemented by a subclass to
        perform some completion action; the default is to do nothing.

        Args:
            dataset: The associated Dataset object.
            params: Type-normalized client parameters
            summary: The summary document of the operation:
                ok      Count of successful actions
                failure Count of failing actions
        """
        pass

    def _analyze_bulk(self, results: Iterator[tuple[bool, Any]]) -> BulkResults:
        """Elasticsearch returns one response result per action. Each is a
        JSON document where the first-level key is the action name
        ("update", "delete", etc.) and the value of that key includes the
        action's "status", "_index", etc; and, on failure, an "error" key
        the value of which gives the type and reason for the failure.

        We assume there will be a single first-level key corresponding to
        the action generated by the subclass and we use that without any
        validation to access the status information.

        Internally report a summary of successes and Elasticsearch failure
        reasons: this will look something like

        {
          "ok": {
            "index1": 1,
            "index2": 500,
            ...
          },
          "elasticsearch failure reason 1": {
            "index2": 5,
            "index5": 10
            ...
          },
          "elasticsearch failure reason 2": {
            "index3": 2,
            "index4": 15
            ...
          }
        }
        """
        report = defaultdict(lambda: defaultdict(int))
        errors = 0
        count = 0

        for ok, response in results:
            count += 1
            u = response[self.action]
            status = "ok"
            if "error" in u:
                e = u["error"]
                # The bulk helper seems to return a stringified exception
                # as the "error" key value, at least in some cases. The
                # documentation is not entirely clear, so to be safe this
                # handles either a stringified exception or the standard
                # Elasticsearch server bulk action response, where "error"
                # is a dict with details. If the type of "error" isn't
                # either of these, just stringify it.
                #
                # For the stringified exception, we try to extract the
                # leading exception name (e.g., 'ConnectionError(...)') for
                # a simpler and more readable error report key; if the
                # pattern doesn't match, use the entire string.
                if isinstance(e, str):
                    match = self.EXCEPTION_NAME.match(e)
                    if match:
                        status = match[1]
                    else:
                        status = e
                elif isinstance(e, dict) and "reason" in e:
                    status = e["reason"]
                else:
                    status = str(e)
                errors += 1
            index = u["_index"]
            report[status][index] += 1
        return BulkResults(errors=errors, count=count, report=report)

    def _post(self, params: ApiParams, _) -> Response:
        """
        Perform the requested POST operation, and handle any exceptions.

        This is called by the ApiBase post() method through its dispatch
        method, which provides parameter validation.

        NOTE: This method relies on a ParamType.DATASET parameter being part of
        the POST API Schema defined by any subclass that extends this base
        class, and the POST schema must select DATASET authorization.
        (This is checked by the constructor.)

        Args:
            params: Type-normalized client parameters
            _: Original incoming Request object (not used)

        Returns:
            Response to return to client
        """
        klasname = self.__class__.__name__

        # Our schema requires a valid dataset and uses it to authorize access;
        # therefore the unconditional dereference is assumed safe.
        dataset = self.schemas.get_param_by_type(
            API_METHOD.POST, ParamType.DATASET, params
        ).value

        if self.require_stable and dataset.state.mutating:
            raise APIAbort(
                HTTPStatus.CONFLICT, f"Dataset state {dataset.state.name} is mutating"
            )

        map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)

        # If we don't have an Elasticsearch index-map, then the dataset isn't
        # indexed and we skip the Elasticsearch actions.
        if map:
            # Build an Elasticsearch instance to manage the bulk update
            elastic = Elasticsearch(self.elastic_uri)
            self.logger.info("Elasticsearch {} [{}]", elastic, VERSION)

            # NOTE: because both generate_actions and streaming_bulk return
            # generators, the entire sequence is inside a single try block.
            try:
                results = helpers.streaming_bulk(
                    elastic,
                    self.generate_actions(params.body, dataset, map),
                    raise_on_exception=False,
                    raise_on_error=False,
                )
                report = self._analyze_bulk(results)
            except Exception as e:
                self.logger.exception(
                    "{}: exception {} occurred during the Elasticsearch request",
                    klasname,
                    type(e).__name__,
                )
                raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
        elif self.require_map:
            raise APIAbort(
                HTTPStatus.CONFLICT,
                f"Dataset {self.action} requires Indexed state ({dataset.state.name})",
            )
        else:
            report = BulkResults(errors=0, count=0, report={})

        summary = {"ok": report.count - report.errors, "failure": report.errors}

        # Let the subclass complete the operation
        try:
            self.complete(dataset, params.body, summary)
        except Exception as e:
            self.logger.exception(
                "{}: exception {} occurred during bulk operation completion",
                klasname,
                type(e).__name__,
            )
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)

        # Return the summary document as the success response, or abort with an
        # internal error if we weren't 100% successful. Some elasticsearch
        # documents may have been affected, but the client will be able to try
        # again.
        #
        # TODO: switching to `pyesbulk` will automatically handle retrying on
        # non-terminal errors, but this requires some cleanup work on the
        # pyesbulk side.
        if report.errors > 0:
            self.logger.error(
                "{}:dataset {}: {} successful document actions and {} failures: {}",
                klasname,
                dataset,
                report.count - report.errors,
                report.errors,
                json.dumps(report.report),
            )
            raise APIAbort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Failed to update {report.errors} out of {report.count} documents",
            )
        self.logger.info(
            "{}:dataset {}: {} successful document actions",
            klasname,
            dataset,
            report.count,
        )
        return jsonify(summary)
