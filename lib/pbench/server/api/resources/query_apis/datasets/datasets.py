from collections import defaultdict
from http import HTTPStatus

from flask import current_app, jsonify, Response

from pbench.server import JSONOBJECT, OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAttributes,
    ApiAuthorizationType,
    APIInternalError,
    ApiMethod,
    ApiParams,
    ApiSchema,
    AuditContext,
    MissingParameters,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import ApiContext
from pbench.server.api.resources.query_apis.datasets import IndexMapBase
import pbench.server.auth.auth as Auth
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.audit import AuditReason, AuditStatus, AuditType
from pbench.server.database.models.datasets import (
    Operation,
    OperationName,
    OperationState,
)
from pbench.server.sync import Sync


class Datasets(IndexMapBase):
    """Delete or update a Pbench dataset

    Delete a dataset or change the owner and access of a Pbench dataset by modifying
    the owner and/or access in the Dataset table and in each Elasticsearch document
    "authorization" sub-document associated with the dataset

    Called as `POST /api/v1/datasets/{resource_id}?access=public&owner=user`
    or DELETE /api/v1/datasets/{resource_id}
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.POST,
                OperationCode.UPDATE,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True),
                ),
                query_schema=Schema(
                    Parameter("access", ParamType.ACCESS, required=False),
                    Parameter("owner", ParamType.USER, required=False),
                ),
                audit_type=AuditType.DATASET,
                audit_name="update",
                authorization=ApiAuthorizationType.DATASET,
                attributes=ApiAttributes(
                    "update",
                    OperationName.UPDATE,
                    require_stable=True,
                    require_map=True,
                ),
            ),
            ApiSchema(
                ApiMethod.DELETE,
                OperationCode.DELETE,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True),
                ),
                audit_type=AuditType.DATASET,
                audit_name="delete",
                authorization=ApiAuthorizationType.DATASET,
                attributes=ApiAttributes(
                    "delete",
                    OperationName.DELETE,
                    require_stable=True,
                    require_map=False,
                ),
            ),
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                authorization=ApiAuthorizationType.DATASET,
                attributes=ApiAttributes(
                    "get",
                    None,
                    require_stable=False,
                    require_map=True,
                ),
            ),
        )

    def assemble(self, params: ApiParams, context: ApiContext) -> JSONOBJECT:
        """Construct an Elasticsearch query to GET/UPDATE/DELETE documents

        This assembly handles three related cases:

        1. To update the access or ownership of a dataset, using the
           _update_by_query operation to find all indexed documents owned by
           the specified dataset and update their "authorization" subdocument
           with a "painless" script.
        2. To delete a dataset, using the _delete_by_query operation to find
           and delete all indexed documents owned by the specified dataset.
        3. An almost-nearly-free diagnostic API to return all indexed documents
           owned by a specified dataset.

        All three operations are based on the same Elasticsearch query
        expression, which searches the set of indices containing documents for
        the specified dataset for documents owned by the dataset resource_id
        (MD5).

        NOTE: while most index document templates record the owning dataset
        resource_id as "run.id", the TOC document records it as
        "run_data_parent", and we need to match against either.
        """

        dataset = context["dataset"]
        auditing: AuditContext = context["auditing"]
        action = context["attributes"].action
        context["action"] = action
        access = None
        owner = None
        elastic_options = {"ignore_unavailable": "true"}

        if action != "get":
            elastic_options["refresh"] = "true"
            operations = Operation.by_state(dataset, OperationState.WORKING)
            if context["attributes"].require_stable and operations:
                raise APIAbort(
                    HTTPStatus.CONFLICT,
                    f"Dataset is working on {','.join(o.name.name for o in operations)}",
                )
            component = context["attributes"].operation_name
            sync = Sync(logger=current_app.logger, component=component)
            try:
                sync.update(dataset=dataset, state=OperationState.WORKING)
            except Exception as e:
                current_app.logger.warning(
                    "{} {} unable to set {} operational state: '{}'",
                    component,
                    dataset,
                    OperationState.WORKING.name,
                    e,
                )
                raise APIInternalError(
                    f"can't set {OperationState.WORKING.name} on {dataset.name}: {str(e)!r} "
                )
            context["sync"] = sync
            if action == "update":
                access = params.query.get("access")
                owner = params.query.get("owner")
                if not access and not owner:
                    raise MissingParameters(["access", "owner"])

                if owner and owner != dataset.owner_id:
                    auth_user = Auth.token_auth.current_user()
                    if not auth_user.is_admin():
                        raise APIAbort(
                            HTTPStatus.FORBIDDEN,
                            "ADMIN role is required to change dataset ownership",
                        )

                if access:
                    auditing.add_attribute("access", access)
                    context["access"] = access
                else:
                    access = dataset.access
                if owner:
                    auditing.add_attribute("owner", owner)
                    context["owner"] = owner
                else:
                    owner = dataset.owner_id

        # Get the Elasticsearch indices occupied by the dataset.
        #
        # We postprocess UPDATE and DELETE even without any indexed documents
        # in order to update the Dataset object, so tell get_index not to fail
        # in that case, and return an empty query to disable the Elasticsearch
        # call.
        #
        # It's important that all context fields required for postprocessing
        # of unindexed datasets have been set before this!
        indices = self.get_index(dataset, ok_no_index=True)
        context["indices"] = indices
        if not indices:
            return {}

        json = {
            "path": None,
            "kwargs": {
                "json": {
                    "query": {
                        "dis_max": {
                            "queries": [
                                {"term": {"run.id": dataset.resource_id}},
                                {"term": {"run_data_parent": dataset.resource_id}},
                            ]
                        }
                    }
                },
                "params": elastic_options,
            },
        }

        if action == "update":
            json["path"] = f"{indices}/_update_by_query"
            json["kwargs"]["json"]["script"] = {
                "source": "ctx._source.authorization=params.authorization",
                "lang": "painless",
                "params": {"authorization": {"access": access, "owner": owner}},
            }
        elif action == "get":
            json["path"] = f"{indices}/_search"
        elif action == "delete":
            json["path"] = f"{indices}/_delete_by_query"
        else:
            raise APIInternalError(f"requested action {action!r} is unknown")

        current_app.logger.info("{} assembled {}", dataset.name, json)
        return json

    def postprocess(self, es_json: JSONOBJECT, context: ApiContext) -> Response:
        """Process the Elasticsearch response.

        * For update and delete, this will be a document with a count of
          successful updates and deletions, along with a list of failures
          and some other data. We mostly want to determine whether it was
          100% successful (before updating or deleting the dataset), but
          we also summarize the results for the client.
        * For get, we return a count of documents for each index name.

        Args:
            es_json: the Elasticsearch response document
            context: the API context

        Returns:
            A Flask response object via jsonify()
        """
        action = context["action"]
        dataset = context["dataset"]
        auditing: AuditContext = context["auditing"]
        current_app.logger.info("POSTPROCESS {}: {}", dataset.name, es_json)
        failures = 0
        if action == "get":
            hits = []
            if es_json:
                try:
                    hits = es_json["hits"]["hits"]
                except KeyError as e:
                    raise APIInternalError(
                        f"Can't find search service match data for {dataset.name} ({e}) in {es_json!r}",
                    )
            if not isinstance(hits, list):
                raise APIInternalError(
                    f"search service did not return hits list ({type(hits).__name__})"
                )
            results = defaultdict(int)
            for hit in hits:
                results[hit["_index"]] += 1
            return jsonify(results)
        else:
            if es_json:
                fields = ("deleted", "updated", "total", "version_conflicts")
                results = {f: es_json.get(f, 0) for f in fields}
                failures = len(es_json["failures"]) if "failures" in es_json else 0
                results["failures"] = failures
            else:
                results = {
                    "deleted": 0,
                    "updated": 0,
                    "total": 0,
                    "version_conflicts": 0,
                    "failures": 0,
                }
            auditing.add_attribute("results", results)

            if failures == 0:
                if action == "update":
                    access = context.get("access")
                    if access:
                        dataset.access = access
                    owner = context.get("owner")
                    if owner:
                        dataset.owner_id = owner
                    try:
                        dataset.update()
                    except Exception as e:
                        raise APIInternalError(
                            f"Unable to update dataset {dataset.name}: {str(e)!r}"
                        ) from e
                elif action == "delete":
                    try:
                        cache_m = CacheManager(self.config, current_app.logger)
                        cache_m.delete(dataset.resource_id)
                        dataset.delete()

                        # Tell caller not to update operational state for the deleted
                        # dataset.
                        del context["sync"]
                    except Exception as e:
                        raise APIInternalError(
                            f"Unable to delete dataset {dataset.name}: {str(e)!r}"
                        ) from e

            # The DELETE API removes the "sync" context on success to signal
            # that the operations table rows no longer exist, so check; but if
            # it's still set then our `sync` local is valid and we want to get
            # it out of "WORKING" state.
            sync = context.get("sync")
            if sync:
                if failures:
                    state = OperationState.FAILED
                    message = f"Unable to {action} some indexed documents"
                else:
                    state = OperationState.OK
                    message = None
                try:
                    sync.update(dataset=dataset, state=state, message=message)
                    del context["sync"]
                except Exception as e:
                    auditing.set_error(str(e), reason=AuditReason.INTERNAL)
                    auditing.status = AuditStatus.WARNING
                    raise APIInternalError(
                        f"Unexpected sync error {dataset.name} {str(e)!r}"
                    ) from e

            # Return the summary document as the success response, or abort with an
            # internal error if we tried to operate on Elasticsearch documents but
            # experienced total failure. Either way, the operation can be retried
            # if some documents failed to update.
            if results["failures"] and results["failures"] == results["total"]:
                auditing.status = AuditStatus.WARNING
                auditing.reason = AuditReason.INTERNAL
                auditing.add_attribute(
                    "message", f"Unable to {action} some indexed documents"
                )
                raise APIInternalError(
                    f"Failed to {action} any of {results['total']} "
                    f"Elasticsearch documents: {es_json}"
                )

        # construct response object
        return jsonify(results)
