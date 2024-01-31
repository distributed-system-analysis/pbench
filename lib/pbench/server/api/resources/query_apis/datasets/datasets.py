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
    MissingParameters,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import ApiContext, PostprocessError
from pbench.server.api.resources.query_apis.datasets import IndexMapBase
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
        action = context["attributes"].action
        get_action = action == "get"
        context["action"] = action
        audit_attributes = {}
        access = None
        owner = None
        elastic_options = {"ignore_unavailable": "true"}

        if not get_action:
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
                raise APIAbort(HTTPStatus.CONFLICT, "Unable to set operational state")
            context["sync"] = sync
            context["auditing"]["attributes"] = audit_attributes
            if action == "update":
                access = params.query.get("access")
                owner = params.query.get("owner")
                if not access and not owner:
                    raise MissingParameters(["access", "owner"])

                if access:
                    audit_attributes["access"] = access
                    context["access"] = access
                else:
                    access = dataset.access
                if owner:
                    audit_attributes["owner"] = owner
                    context["owner"] = owner
                else:
                    owner = dataset.owner_id

        # Get the Elasticsearch indices occupied by the dataset. If there are
        # none, return with an empty query to disable the Elasticsearch call.
        #
        # It's important that all context fields required for postprocessing
        # of unindexed datasets have been set before this!
        indices = self.get_index(dataset, ok_no_index=(not get_action))
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
            painless = "ctx._source.authorization=params.authorization"
            script_params = {"authorization": {"access": access, "owner": owner}}
            script = {"source": painless, "lang": "painless", "params": script_params}
            json["path"] = f"{indices}/_update_by_query"
            json["kwargs"]["json"]["script"] = script
        elif action == "get":
            json["path"] = f"{indices}/_search"
        elif action == "delete":
            json["path"] = f"{indices}/_delete_by_query"
        else:
            raise APIInternalError(f"requested action {action!r} is unknown")

        current_app.logger.info("{} assembled {}", dataset.name, json)
        return json

    def postprocess(self, es_json: JSONOBJECT, context: ApiContext) -> Response:
        """
        Returns a summary of the returned Elasticsearch query results, showing
        the list of dictionaries with user selected fields from request json as keys
        Note: id field is added by server by default whereas other fields are client-selected.

        [
            {
                "id": "1c25e9f5b5dfc1ffb732931bf3899878",
                "@timestamp": "2021-07-12T22:44:19.562354",
                "run": {
                    "controller": "dhcp31-171.example.com",
                    "name": "pbench-user-benchmark_npalaska-dhcp31-171_2021.07.12T22.44.19",
                },
                "@metadata": {
                    "controller_dir": "dhcp31-171.example.com"
                }
            },
        ]
        """
        # If there are no matches for the user, query, and time range,
        # return the empty list rather than failing.
        action = context["action"]
        dataset = context["dataset"]
        failures = 0
        if action == "get":
            try:
                count = es_json["hits"]["total"]["value"]
                if int(count) == 0:
                    current_app.logger.info("No data returned by Elasticsearch")
                    return jsonify([])
            except KeyError as e:
                raise PostprocessError(
                    HTTPStatus.BAD_REQUEST,
                    f"Can't find Elasticsearch match data {e} in {es_json!r}",
                )
            except ValueError as e:
                raise PostprocessError(
                    HTTPStatus.BAD_REQUEST,
                    f"Elasticsearch hit count {count!r} value: {e}",
                )
            results = []
            for hit in es_json["hits"]["hits"]:
                s = hit["_source"]
                s["id"] = hit["_id"]
                results.append(s)
        else:
            if es_json:
                fields = ("deleted", "updated", "total", "version_conflicts")
                results = {f: es_json[f] if f in es_json else None for f in fields}
                failures = len(es_json["failures"]) if "failures" in es_json else 0
                results["failures"] = failures
                context["auditing"]["attributes"]["results"] = results

                current_app.logger.info(
                    "{} {} results {}, failures {}",
                    dataset.name,
                    action,
                    results,
                    es_json.get("failures"),
                )
            else:
                results = {
                    "deleted": 0,
                    "updated": 0,
                    "total": 0,
                    "version_conflicts": 0,
                    "failures": 0,
                }

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
                            f"unable to update dataset {dataset.name}: {str(e)!r}"
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
                            f"unable to delete dataset {dataset.name}: {str(e)!r}"
                        ) from e

            # The DELETE API removes the "sync" context on success to signal
            # that the operations table rows no longer exist, so check; but if
            # it's still set then our `sync` local is valid and we want to get
            # it out of "WORKING" state.
            sync = context.get("sync")
            auditing = context["auditing"]
            if sync:
                state = OperationState.OK if not failures else OperationState.FAILED
                try:
                    sync.update(dataset=dataset, state=state)
                except Exception as e:
                    auditing["attributes"] = {"message": str(e)}
                    auditing["status"] = AuditStatus.WARNING
                    auditing["reason"] = AuditReason.INTERNAL
                    raise APIInternalError(f"Unexpected sync unlock error '{e}'") from e

            # Return the summary document as the success response, or abort with an
            # internal error if we tried to operate on Elasticsearch documents but
            # experienced total failure. Either way, the operation can be retried
            # if some documents failed to update.
            if results["failures"] and results["failures"] == results["total"]:
                auditing["status"] = AuditStatus.WARNING
                auditing["reason"] = AuditReason.INTERNAL
                auditing["attributes"][
                    "message"
                ] = f"Unable to {context['attributes'].action} some indexed documents"
                raise APIInternalError(
                    f"Failed to {context['attributes'].action} any of {results['total']} "
                    f"Elasticsearch documents: {es_json}"
                )
            elif sync:
                sync.error(
                    dataset=dataset,
                    message=f"Unable to {action} some indexed documents",
                )
        # construct response object
        return jsonify(results)
