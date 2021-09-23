from collections import Counter, defaultdict
from datetime import datetime
from http import HTTPStatus
from logging import Logger
from typing import Any, Callable, Dict, Iterator, List
from urllib.parse import urljoin

from dateutil import rrule
from dateutil.relativedelta import relativedelta
import elasticsearch
from flask.wrappers import Response
from flask_restful import abort
import requests

from pbench.server import PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.api.resources import (
    API_OPERATION,
    ApiBase,
    JSON,
    PostprocessError,
    Schema,
    SchemaError,
    UnauthorizedAccess,
)
from pbench.server.database.models.datasets import Dataset, DatasetNotFound
from pbench.server.database.models.template import Template
from pbench.server.database.models.users import User

# A type defined to allow the preprocess subclass method to provide shared
# context with the assemble and postprocess methods.
CONTEXT = Dict[str, Any]


class MissingBulkSchemaParameters(SchemaError):
    """
    The subclass schema is missing the required "controller" or dataset "name"
    parameters required to locate a Dataset.
    """

    def __init__(self, subclass_name: str):
        super().__init__()
        self.subclass_name = subclass_name

    def __str__(self) -> str:
        return f"API {self.subclass_name} is missing schema parameters controller and/or name"


class NoSelectedDatasets(Exception):
    """
    Raised by the query builder when the input terms mean that no Elasticsearch
    data could be selected without violating security rules. Most cases are
    handled up-front by schema validation and authorization; edge cases raise
    this exception to trigger logic in the subclass postprocess() method that
    generates an appropriate empty response (e.g., [] or {}).
    """

    def __init__(self, user: str, access: str):
        self.user = user
        self.access = access

    def __str__(self) -> str:
        user = f"user {self.user!r}" if self.user else "unauthorized client"
        return f"Query from {user} for access {self.access!r} cannot produce results"


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

    def _get_user_query(self, parameters: JSON, terms: List[JSON]) -> JSON:
        """
        Generate the "query" node for an Elasticsearch document query.

        In most cases this just adds a "term" within the "query"/"filter" node.
        Several queries use an "and" term including user and access, which
        generates two new "term" nodes. The most complicated is a query which
        doesn't include user or access for an authorized user, which must
        return all datasets "owned by the user or with access public".

        Note that if a "user" JSON parameter is specified, the common
        infrastructure has already checked that there's an authentication token
        and that the token represents a user with access to that specified
        user's data. This method is concerned only with constructing a proper
        Elasticsearch query to represent the authenticated restrictions.

        Specific cases for user and access values:

            {}: defaulting both user and access
                All private + public regardless of owner

                ADMIN: all datasets
                AUTHORIZED: all owner:mine OR access:public
                UNAUTHORIZED: all access:public

            {"user": "drb"}: defaulting access
                All datasets owned by "drb"

                ADMIN: all owner:drb
                AUTHORIZED as drb: all owner:drb
                UNAUTHORIZED (or non-drb): all owner:drb AND access:public

            {"user": "drb, "access": "private"}: private drb
                All datasets owned by "drb" with "private" access

                ADMIN: all owner:drb AND access:private
                AUTHORIZED as drb: all owner:drb AND access:private
                UNAUTHORIZED (or non-drb): NO DATA

            {"user": "drb", "access": "public"}: public drb
                All datasets owned by "drb" with "public" access

                ADMIN: all owner:drb AND access:public
                AUTHORIZED as drb: all owner:drb AND access:public
                UNAUTHORIZED (or non-drb): all owner:drb AND access:public

                TODO: Need to decide if this is a security issue. Do we want to
                hide the existence of other users here? E.g., should the
                UNAUTHORIZED case return NO DATA? And if so, should there be a
                difference between UNAUTHORIZED and AUTHORIZED for some other
                user? (And, NOTE, specifying a "user" parameter, either without
                authentication or with non-ADMIN authentication where the user
                parameter doesn't match the specified "user" parameter, will
                result in an UnverifiedUser exception during schema validation,
                so we won't reach this point. That is, changes must be made if
                we want to ALLOW these requests.)

            {"access": "private"}: all private data
                All datasets with "private" access regardless of user

                ADMIN: all access:private
                AUTHORIZED: all owner:"me" AND access:private
                UNAUTHORIZED: NO DATA

            {"access": "public"}: all public data
                All datasets with "public" access

                ADMIN: all access:public
                AUTHORIZED: all access:public
                UNAUTHORIZED: all access:public

        The "or" structure for the AUTHORIZED case of {} is the most
        complicated query: this requires a nested must/should structure with the
        constant_score option and defines the interface style of this method,
        which accepts query "term" nodes from the subclass to be fit into a
        "query" node rather than simply patching new "term" nodes into an
        existing "query" node. This structure translates to "must have" both
        the basic subclass query "term" nodes AND either (the username "term"
        node OR the access "term" node). E.g.,

        "query": {
            "constant_score": {  # Disable scoring
                "filter": {
                    "bool": {  # Enter outer boolean scope
                        "must": [ # Combine subquery terms with authorization
                            {
                                "bool": {  # Nested authorization OR (should)
                                    "should": [
                                        {
                                            "term": {
                                                "authorization.owner": "5"
                                            }
                                        },
                                        {
                                            "term": {
                                                "authorization.access": "public"
                                            }
                                        }
                                    ]
                                }
                            },
                            {   # The subclass term becomes a second AND term (must)
                                "range": {
                                    "@timestamp": {
                                    "gte": "2021-09-01",
                                    "lte": "2021-10-28"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        },

        Args:
            JSON query parameters containing keys:
                "user": Pbench internal username if present and not None; if
                    omitted, doesn't restrict search on user.
                "access": Access category, "public" or "private"; defaults to
                    don't-care
            terms: A list of JSON nodes describing the Elasticsearch "terms"
                that must be matched for the query. These will be inserted
                within a "must" list for the generated query.

        Raises:
            NoSelectedDatasets: This is raised when there is no possible output
                from a query (e.g., private data queries from an unauthorized
                client). There's no point in generating a query or calling
                Elasticsearch (which would require an impossible combination
                of terms resulting in no output but no errors). The _call()
                method will handle this by calling postprocess() with an empty
                query response that must trigger the subclass to act as if
                there were no hits or aggregations.

        Returns:
            An assembled Elasticsearch "query" mode that includes the necessary
            user/access terms.
        """
        user = parameters.get("user")
        access = parameters.get("access")
        authorized_user: User = Auth.token_auth.current_user()
        is_admin = authorized_user.is_admin() if authorized_user else False
        query = {}
        must = [t for t in terms]  # Create a new list, which we'll modify

        if access is None and user is None:
            # {}
            if is_admin:
                # ADMIN needs no authorization search terms: all is permitted,
                # so we need only the subclass query terms.
                query["bool"] = {"filter": must}
            else:
                if not authorized_user:
                    # An unauthorized client sees all public data
                    must.append({"term": {"authorization.access": "public"}})
                    query["bool"] = {"filter": must}
                else:
                    # An authorized user can see their own private data plus
                    # public data ("OR" relationship)
                    must.append(
                        {
                            "bool": {
                                "should": [
                                    {
                                        "term": {
                                            "authorization.owner": str(
                                                authorized_user.id
                                            )
                                        }
                                    },
                                    {"term": {"authorization.access": "public"}},
                                ]
                            }
                        }
                    )
                    query["constant_score"] = {"filter": {"bool": {"must": must}}}
        elif access is None:
            # {"user": "xxx"}
            must.append({"term": {"authorization.owner": user}})
            query["bool"] = {"filter": must}
        elif user is None:
            # {"access": "xxx"}
            if access == Dataset.PUBLIC_ACCESS:
                must.append({"term": {"authorization.access": Dataset.PUBLIC_ACCESS}})
            else:
                if not authorized_user:
                    # An unauthorized user can never view access:private data,
                    # but schema validation wasn't able to detect this so we
                    # raise our special exception to skip the query.
                    raise NoSelectedDatasets(user, access)
                must.append({"term": {"authorization.access": Dataset.PRIVATE_ACCESS}})
                if not is_admin:
                    # A non-admin user can only see their own private data
                    must.append(
                        {"term": {"authorization.owner": str(authorized_user.id)}}
                    )
            query["bool"] = {"filter": must}
        else:
            # {"access": "xxx", "user": "xxx"}
            must.append({"term": {"authorization.access": access}})
            must.append({"term": {"authorization.owner": user}})
            query["bool"] = {"filter": must}
        return query

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
            self.logger.info(
                "ASSEMBLE returned URL {!r}, {!r}", url, es_request.get("json")
            )
        except NoSelectedDatasets as e:
            # The query builder reports that no datasets can be found; skip
            # the Elasticsearch query and tell postprocess to build an empty
            # client response as appropriate.
            self.logger.info("{} query builder reports no matches: {}", klasname, e)
            context["NODATA"] = True
        except Exception as e:
            self.logger.exception("{} assembly failed: {}", klasname, e)
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        try:
            if not context.get("NODATA", False):
                # perform the Elasticsearch query
                es_response = method(url, **es_request["kwargs"])
                self.logger.debug(
                    "ES query response {}:{}",
                    es_response.reason,
                    es_response.status_code,
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
        action: str = None,
        role: API_OPERATION = API_OPERATION.UPDATE,
    ):
        """
        Base class constructor.

        This method assumes and requires that a dataset will be located using
        the controller and dataset name, so "controller" and "name" string-type
        parameters must be defined in the subclass schema.

        Args:
            config: server configuration
            logger: logger object
            schema: API schema: for example,
                    Schema(
                        Parameter("controller", ParamType.STRING, required=True),
                        Parameter("name", ParamType.STRING, required=True),
                        ...
                    )
            action: the Elasticsearch bulk operation action ("update",
                "delete", etc.)
            role: specify the API role, defaulting to UPDATE
        """
        super().__init__(config, logger, schema, role=role)
        self.node = {
            "host": config.get("elasticsearch", "host"),
            "port": config.get("elasticsearch", "port"),
        }
        self.action = action

        if "controller" not in schema or "name" not in schema:
            raise MissingBulkSchemaParameters(self.__class__.__name__)

    def generate_actions(self, json_data: JSON, dataset: Dataset) -> Iterator[dict]:
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
            json_data: The original query JSON parameters based on the subclass
                schema.
            dataset: The associated Dataset object

        Returns:
            Sequence of Elasticsearch bulk action dict objects
        """
        raise NotImplementedError()

    def complete(self, dataset: Dataset, json_data: JSON, summary: JSON) -> None:
        """
        Complete a bulk Elasticsearch operation, perhaps by modifying the
        source Dataset resource.

        This is an abstract method that may be implemented by a subclass to
        perform some completion action; the default is to do nothing.

        Args:
            dataset: The associated Dataset object.
            json_data: The original query JSON parameters based on the subclass
                schema.
            summary: The summary document of the operation:
                ok      Count of successful actions
                failure Count of failing actions
        """
        pass

    def _post(self, json_data: JSON, _) -> Response:
        """
        Perform the requested POST operation, and handle any exceptions.

        This is called by the ApiBase post() method through its dispatch
        method, which provides parameter validation.

        NOTE: This method relies on the "controller" and "name" JSON parameters
        being part of the API Schema defined by any subclass that extends this
        base class. (This is checked by the constructor.)

        Args:
            json_data: Type-normalized client JSON input
                controller: Dataset controller name
                name: Dataset name
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
        elastic = elasticsearch.Elasticsearch(self.node)

        # Internally report a summary of successes and Elasticsearch failure
        # reasons: this will look something like
        #
        # {
        #   "ok": {
        #     "index1": 1,
        #     "index2": 500,
        #     ...
        #   },
        #   "elasticsearch failure reason 1": {
        #     "index2": 5,
        #     "index5": 10
        #     ...
        #   },
        #   "elasticsearch failure reason 2": {
        #     "index3": 2,
        #     "index4": 15
        #     ...
        #   }
        # }
        report = defaultdict(Counter)
        count = 0
        error_count = 0

        # NOTE: because streaming_bulk is given a generator, and also
        # returns a generator, we consume the entire sequence within the
        # `try` block to catch failures.
        try:
            # Pass the bulk command generator to the helper
            results = elasticsearch.helpers.streaming_bulk(
                elastic,
                self.generate_actions(json_data, dataset),
                raise_on_exception=False,
                raise_on_error=False,
            )

            # Elasticsearch returns one response result per action. Each is a
            # JSON document where the first-level key is the action name
            # ("update", "delete", etc.) and the value of that key includes the
            # action's "status", "_index", etc; and, on failure, an "error" key
            # the value of which gives the type and reason for the failure.
            #
            # We assume there will be a single first-level key corresponding to
            # the action generated by the subclass and we use that without any
            # validation to access the status information.
            for ok, response in results:
                count += 1
                u = response[self.action]
                status = "ok"
                if "error" in u:
                    e = u["error"]
                    status = e["reason"]
                    error_count += 1
                report[status][u["_index"]] += 1
        except Exception as e:
            self.logger.exception(
                "{}: exception {} occurred during the Elasticsearch request: report {}",
                klasname,
                type(e).__name__,
                report,
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        summary = {"ok": count - error_count, "failure": error_count}

        # Let the subclass complete the operation
        self.complete(dataset, json_data, summary)

        # Return the summary document as the success response, or abort with an
        # internal error if we weren't 100% successful. Some elasticsearch
        # documents may have been affected, but the client will be able to try
        # again.
        #
        # TODO: switching to `pyesbulk` will automatically handle retrying on
        # non-terminal errors, but this requires some cleanup work on the
        # pyesbulk side.
        if error_count > 0:
            self.logger.error(
                "{}:dataset {}: {} successful document updates and {} failures: {}",
                klasname,
                dataset,
                count - error_count,
                error_count,
                report,
            )
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                message=f"{error_count:d} of {count:d} Elasticsearch document UPDATE operations failed",
                data=summary,
            )

        self.logger.info(
            "{}:dataset {}: {} successful document updates", klasname, dataset, count
        )
        return summary
