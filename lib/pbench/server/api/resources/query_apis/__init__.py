from datetime import datetime
from http import HTTPStatus
from typing import Callable, List, Optional
from urllib.parse import urljoin
from urllib.request import Request

from dateutil import rrule
from dateutil.relativedelta import relativedelta
from flask import current_app
from flask.wrappers import Response
import requests

from pbench.server import JSONOBJECT, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiBase,
    ApiContext,
    APIInternalError,
    ApiParams,
    ApiSchema,
    SchemaError,
    UnauthorizedAccess,
)
import pbench.server.auth.auth as Auth
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.templates import Template
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

    def __init__(self, status: int, message: str, data: Optional[JSONOBJECT] = None):
        super().__init__(
            f"Postprocessing error returning {status}: {message!r} [{data}]"
        )
        self.status = status
        self.message = message
        self.data = data


class ElasticBase(ApiBase):
    """
    A base class for Elasticsearch queries that allows subclasses to provide
    custom pre- and post-processing.

    This class extends the ApiBase class in order to connect the POST
    and GET methods to Flask's URI routing algorithms. It implements a common
    mechanism for calling Elasticsearch and processing errors.

    Hooks are defined for subclasses extending this class to "preprocess"
    the query, to "assemble" the Elasticsearch request payload from Pbench
    server data and the client's JSON payload, and to "postprocess" a
    successful response payload from Elasticsearch.

    Note that `preprocess` can provide context that's passed to the `assemble`
    and `postprocess` methods.
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
                    ApiMethod.GET,
                    OperationCode.READ,
                    query_schema=Schema(Parameter("start", ParamType.DATE)),
                    uri_schema=Schema(Parameter("dataset", ParamType.DATASET))
                ),
                ApiSchema(
                    ApiMethod.POST,
                    OperationCode.UPDATE,
                    body_schema=Schema(Parameter("start", ParamType.DATE)),
                    uri_schema=Schema(Parameter("dataset", ParamType.DATASET))
                )
        """
        super().__init__(config, *schemas)
        self.prefix = config.get("Indexing", "index_prefix")
        self.es_url = config.get("Indexing", "uri")
        self.ca_bundle = config.get("Indexing", "ca_bundle")

    @staticmethod
    def _build_elasticsearch_query(
        user: Optional[str], access: Optional[str], terms: List[JSONOBJECT]
    ) -> JSONOBJECT:
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

            {"user": "drb", "access": "private"}: private drb
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

        filter_list = terms.copy()
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
            filter_list.append(combo_term)
        else:
            if access_term:
                filter_list.append(access_term)
            if user_term:
                filter_list.append(user_term)
        return {"bool": {"filter": filter_list}}

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

    def assemble(self, params: ApiParams, context: ApiContext) -> JSONOBJECT:
        """
        Assemble the Elasticsearch parameters.

        This is an abstract method that must be implemented by a subclass.

        Args:
            params: Type-normalized client parameters
            context: API context dictionary

        Raises:
            Any errors in the `assemble` method shall be reported by exceptions
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

    def postprocess(self, es_json: JSONOBJECT, context: ApiContext) -> Response:
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
            The Flask response object (e.g., from 'jsonify')
        """
        raise NotImplementedError()

    def _call(
        self, method: Callable, params: ApiParams, context: ApiContext
    ) -> Response:
        """
        Perform the requested call to Elasticsearch, and handle any exceptions.

        Args:
            method: requests package callable (e.g., requests.get)
            params: Type-normalized client parameters
            context: API context dictionary

        Returns:
            Post-processed JSON body to return to client
        """
        klasname = self.__class__.__name__
        try:
            self.preprocess(params, context)
            current_app.logger.debug("PREPROCESS returns {}", context)
        except UnauthorizedAccess as e:
            raise APIAbort(e.http_status, str(e))
        except KeyError as e:
            raise APIInternalError(f"problem in preprocess, missing {e}") from e

        url = None
        try:
            # prepare payload for Elasticsearch query
            es_request = self.assemble(params, context)
            if not es_request:
                current_app.logger.info("ASSEMBLE disabled Elasticsearch call")
            else:
                path = es_request.get("path")
                url = urljoin(self.es_url, path)
                current_app.logger.info(
                    "ASSEMBLE returned URL {!r}, {!r}",
                    url,
                    es_request.get("kwargs").get("json"),
                )
        except Exception as e:
            if isinstance(e, APIAbort):
                raise
            raise APIInternalError("Elasticsearch assembly error") from e

        es_response = None
        json_response = {}
        if es_request:
            try:
                # perform the Elasticsearch query
                es_response: requests.Response = method(
                    url, **es_request["kwargs"], verify=self.ca_bundle
                )
                current_app.logger.debug(
                    "ES query response {}:{}",
                    es_response.reason,
                    es_response.status_code,
                )
                es_response.raise_for_status()
                json_response = es_response.json()
            except requests.exceptions.HTTPError as e:
                current_app.logger.error(
                    "{} HTTP error {} from Elasticsearch request {} -> {}",
                    klasname,
                    e,
                    es_request,
                    e.response.text if e.response else "<unknown>",
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
                    HTTPStatus.BAD_GATEWAY,
                    "Network problem, could not reach Elasticsearch",
                )
            except requests.exceptions.Timeout:
                current_app.logger.error(
                    "{}: connection timed out during the Elasticsearch request",
                    klasname,
                )
                raise APIAbort(
                    HTTPStatus.GATEWAY_TIMEOUT,
                    "Connection timed out, could reach Elasticsearch",
                )
            except requests.exceptions.InvalidURL as e:
                raise APIInternalError(f"Invalid Elasticsearch URL {url}") from e
            except Exception as e:
                raise APIInternalError(f"Unexpected backend error '{e}'") from e

        try:
            # postprocess Elasticsearch response
            return self.postprocess(json_response, context)
        except PostprocessError as e:
            msg = f"{klasname}: {str(e)}"
            current_app.logger.error("{}", msg)
            raise APIAbort(e.status, msg)
        except Exception as e:
            raise APIInternalError(f"Unexpected backend exception '{e}'") from e

    def _post(self, params: ApiParams, req: Request, context: ApiContext) -> Response:
        """Handle a Pbench server POST operation involving Elasticsearch

        The assembly and post-processing of the Elasticsearch query are
        handled by the subclasses through the assemble() and postprocess()
        methods; we rely on the ApiBase superclass to provide basic JSON
        parameter validation and normalization.

        Args:
            params: The API HTTP method parameters
            req: The flask Request object containing payload and headers
            context: The API context dictionary
        """
        context["request"] = req
        return self._call(requests.post, params, context)

    def _get(self, params: ApiParams, req: Request, context: ApiContext) -> Response:
        """Handle a GET operation involving a call to Elasticsearch

        The post-processing of the Elasticsearch query is handled by the
        subclasses through their postprocess() methods.

        Args:
            params: The API HTTP method parameters
            req: The flask Request object containing payload and headers
            context: The API context dictionary
        """
        context["request"] = req
        return self._call(requests.get, params, context)
