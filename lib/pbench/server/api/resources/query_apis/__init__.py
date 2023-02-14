from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
import json
import re
from typing import Any, Callable, Iterator, List, Optional
from urllib.parse import urljoin
from urllib.request import Request

from dateutil import rrule
from dateutil.relativedelta import relativedelta
from elasticsearch import Elasticsearch, helpers, VERSION
from flask import current_app, jsonify
from flask.wrappers import Response
import requests

from pbench.server import JSON, JSONOBJECT, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiBase,
    ApiContext,
    APIInternalError,
    ApiMethod,
    ApiParams,
    ApiSchema,
    MissingParameters,
    ParamType,
    SchemaError,
    UnauthorizedAccess,
    UnauthorizedAdminAccess,
)
import pbench.server.auth.auth as Auth
from pbench.server.database.database import Database
from pbench.server.database.models.audit import AuditReason, AuditStatus
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    Operation,
    OperationState,
)
from pbench.server.database.models.template import Template
from pbench.server.database.models.users import User


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
        *schemas: ApiSchema,
    ):
        """
        Base class constructor.

        Args:
            config: server configuration
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
        super().__init__(config, *schemas)
        self.prefix = config.get("Indexing", "index_prefix")
        self.es_url = config.get("Indexing", "uri")

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
        current_app.logger.debug(
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
            current_app.logger.debug("QUERY: not self public: {}", access_term)
        elif access:
            access_term = {"term": {"authorization.access": access}}
            if not user and access == Dataset.PRIVATE_ACCESS and not is_admin:
                user_term = {"term": {"authorization.owner": authorized_id}}
            current_app.logger.debug(
                "QUERY: user: {}, access: {}", user_term, access_term
            )
        elif not user and not is_admin:
            combo_term = {
                "dis_max": {
                    "queries": [
                        {"term": {"authorization.owner": authorized_id}},
                        {"term": {"authorization.access": Dataset.PUBLIC_ACCESS}},
                    ]
                }
            }
            current_app.logger.debug("QUERY: {{}} self + public: {}", combo_term)
        else:
            # Either "user" was specified and will be added to the filter,
            # or client is ADMIN and no access restrictions are required.
            current_app.logger.debug("QUERY: {{}} default, user: {}", user_term)

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

    def preprocess(self, params: ApiParams, context: ApiContext) -> None:
        """
        Given the client Request payload, perform any preprocessing activities
        necessary prior to constructing an Elasticsearch query.

        The base class assumes no preprocessing is necessary; this can be
        overridden by subclasses as necessary.

        Args:
            params: Type-normalized client parameters
            context: API context dictionary

        Raises:
            Any errors in the postprocess method shall be reported by
            exceptions which will be logged and will terminate the operation.
        """
        pass

    def assemble(self, params: ApiParams, context: ApiContext) -> JSON:
        """
        Assemble the Elasticsearch parameters.

        This is an abstract method that must be implemented by a subclass.

        Args:
            params: Type-normalized client parameters
            context: API context dictionary

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

    def postprocess(self, es_json: JSON, context: ApiContext) -> JSON:
        """
        Given the Elasticsearch Response object, construct a JSON document to
        be returned to the original caller.

        This is an abstract method that must be implemented by a subclass.

        Args:
            es_json: Elasticsearch Response payload
            context: context: API context dictionary

        Raises:
            Any errors in the postprocess method shall be reported by
            exceptions which will be logged and will terminate the operation.

        Returns:
            The JSON payload to be returned to the caller
        """
        raise NotImplementedError()

    def _call(self, method: Callable, params: ApiParams, context: ApiContext):
        """
        Perform the requested call to Elasticsearch, and handle any exceptions.

        Args:
            method: requests package callable (e.g., requests.get)
            params: Type-normalized client parameters
            context: API context dictionary

        Returns:
            Postprocessed JSON body to return to client
        """
        klasname = self.__class__.__name__
        try:
            self.preprocess(params, context)
            current_app.logger.debug("PREPROCESS returns {}", context)
        except UnauthorizedAccess as e:
            raise APIAbort(e.http_status, str(e))
        except KeyError as e:
            raise APIInternalError(f"problem in preprocess, missing {e}") from e
        try:
            # prepare payload for Elasticsearch query
            es_request = self.assemble(params, context)
            path = es_request.get("path")
            url = urljoin(self.es_url, path)
            current_app.logger.info(
                "ASSEMBLE returned URL {!r}, {!r}",
                url,
                es_request.get("kwargs").get("json"),
            )
        except Exception as e:
            raise APIInternalError("Elasticsearch assembly error") from e

        try:
            # perform the Elasticsearch query
            es_response = method(url, **es_request["kwargs"])
            current_app.logger.debug(
                "ES query response {}:{}",
                es_response.reason,
                es_response.status_code,
            )
            es_response.raise_for_status()
            json_response = es_response.json()
        except requests.exceptions.HTTPError as e:
            current_app.logger.error(
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
            current_app.logger.error(
                "{}: connection refused during the Elasticsearch request", klasname
            )
            raise APIAbort(
                HTTPStatus.BAD_GATEWAY, "Network problem, could not reach Elasticsearch"
            )
        except requests.exceptions.Timeout:
            current_app.logger.error(
                "{}: connection timed out during the Elasticsearch request", klasname
            )
            raise APIAbort(
                HTTPStatus.GATEWAY_TIMEOUT,
                "Connection timed out, could reach Elasticsearch",
            )
        except requests.exceptions.InvalidURL as e:
            raise APIInternalError(f"Invalid Elasticsearch URL {url}") from e
        except Exception as e:
            raise APIInternalError("Unexpected backend error") from e

        try:
            # postprocess Elasticsearch response
            return self.postprocess(json_response, context)
        except PostprocessError as e:
            msg = f"{klasname}: {str(e)}"
            current_app.logger.error("{}", msg)
            raise APIAbort(e.status, msg)
        except Exception as e:
            raise APIInternalError("Unexpected backend exception") from e

    def _post(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Handle a Pbench server POST operation that will involve a call to the
        server's configured Elasticsearch instance. The assembly and
        post-processing of the Elasticsearch query are handled by the
        subclasses through the assemble() and postprocess() methods;
        we rely on the ApiBase superclass to provide basic JSON parameter
        validation and normalization.

        Args:
            method: The API HTTP method
            request: The flask Request object containing payload and headers
            uri_params: URI encoded keyword-arg supplied by the Flask
                framework
        """
        return self._call(requests.post, params, context)

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Handle a GET operation involving a call to the server's Elasticsearch
        instance. The post-processing of the Elasticsearch query is handled
        the subclasses through their postprocess() methods.

        Args:
            method: The API HTTP method
            request: The flask Request object containing payload and headers
            uri_params: URI encoded keyword-arg supplied by the Flask
                framework
        """
        return self._call(requests.get, params, context)


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
        super().__init__(config, *schemas)

        api_name = self.__class__.__name__

        self.elastic_uri = config.get("Indexing", "uri")
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
            ApiMethod.POST,
            ParamType.DATASET,
            ApiParams(),
        )
        if not dset or not dset.parameter.required:
            raise MissingBulkSchemaParameters(
                api_name, "dataset parameter is not defined or not required"
            )
        assert (
            self.schemas[ApiMethod.POST].authorization == ApiAuthorizationType.DATASET
        ), f"API {self.__class__.__name__} authorization type must be DATASET"

    def generate_actions(
        self,
        params: ApiParams,
        dataset: Dataset,
        context: ApiContext,
        map: dict[str, list[str]],
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
            params: Type-normalized client request body JSON
            dataset: The associated Dataset object
            context: The operation's ApiContext
            map: Elasticsearch index document map

        Returns:
            Sequence of Elasticsearch bulk action dict objects
        """
        raise NotImplementedError()

    def complete(
        self, dataset: Dataset, context: ApiContext, summary: JSONOBJECT
    ) -> None:
        """
        Complete a bulk Elasticsearch operation, perhaps by modifying the
        source Dataset resource.

        This is an abstract method that may be implemented by a subclass to
        perform some completion action; the default is to do nothing.

        Args:
            dataset: The associated Dataset object.
            context: The operation's ApiContext
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

    def _post(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
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
            request: Original incoming Request object (not used)
            context: API context

        Returns:
            Response to return to client
        """

        # Our schema requires a valid dataset and uses it to authorize access;
        # therefore the unconditional dereference is assumed safe.
        dataset = self.schemas.get_param_by_type(
            ApiMethod.POST, ParamType.DATASET, params
        ).value

        operation = (
            Database.db_session.query(Operation)
            .filter(
                Operation.dataset_ref == dataset.id,
                Operation.state == OperationState.WORKING,
            )
            .first()
        )
        if self.require_stable and operation:
            raise APIAbort(
                HTTPStatus.CONFLICT,
                f"Dataset is working on {operation.name.name}",
            )

        map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)

        # If we don't have an Elasticsearch index-map, then the dataset isn't
        # indexed and we skip the Elasticsearch actions.
        if map:
            # Build an Elasticsearch instance to manage the bulk update
            elastic = Elasticsearch(self.elastic_uri)
            current_app.logger.info("Elasticsearch {} [{}]", elastic, VERSION)

            # NOTE: because both generate_actions and streaming_bulk return
            # generators, the entire sequence is inside a single try block.
            try:
                results = helpers.streaming_bulk(
                    elastic,
                    self.generate_actions(params, dataset, context, map),
                    raise_on_exception=False,
                    raise_on_error=False,
                )
                report = self._analyze_bulk(results)
            except UnauthorizedAdminAccess as e:
                raise APIAbort(e.http_status, str(e))
            except MissingParameters as e:
                raise APIAbort(e.http_status, str(e))
            except Exception as e:
                raise APIInternalError("Unexpected backend error") from e
        elif self.require_map:
            raise APIAbort(
                HTTPStatus.CONFLICT,
                f"Operation unavailable: dataset {dataset.resource_id} is not indexed.",
            )
        else:
            report = BulkResults(errors=0, count=0, report={})

        summary: JSONOBJECT = {
            "ok": report.count - report.errors,
            "failure": report.errors,
        }
        auditing: dict[str, Any] = context["auditing"]
        attributes: JSONOBJECT = {"summary": summary}
        auditing["attributes"] = attributes

        # Let the subclass complete the operation
        try:
            self.complete(dataset, context, summary)
        except Exception as e:
            attributes["message"] = str(e)
            auditing["status"] = AuditStatus.WARNING
            auditing["reason"] = AuditReason.INTERNAL
            raise APIInternalError("Unexpected completion error") from e

        # Return the summary document as the success response, or abort with an
        # internal error if we tried to operate on Elasticsearch documents but
        # experienced total failure. Either way, the operation can be retried
        # if some documents failed to update.
        #
        # TODO: switching to `pyesbulk` will automatically handle retrying on
        # non-terminal errors, but this requires some cleanup work on the
        # pyesbulk side.
        if report.count and report.errors == report.count:
            auditing["status"] = AuditStatus.WARNING
            auditing["reason"] = AuditReason.INTERNAL
            attributes["message"] = f"Unable to {self.action} some indexed documents"
            raise APIInternalError(
                f"Failed to {self.action} any of {report.count} Elasticsearch documents: {json.dumps(report.report)}"
            )
        return jsonify(summary)
