from typing import Any, Iterator

from flask import current_app

from pbench.server import JSONOBJECT, OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    ApiAttributes,
    ApiAuthorizationType,
    ApiMethod,
    ApiParams,
    ApiSchema,
    MissingParameters,
    Parameter,
    ParamType,
    Schema,
    UnauthorizedAdminAccess,
)
from pbench.server.api.resources.query_apis import ApiContext, ElasticBulkBase
import pbench.server.auth.auth as Auth
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.audit import AuditType
from pbench.server.database.models.datasets import Dataset, OperationName
from pbench.server.database.models.index_map import IndexStream


class Datasets(ElasticBulkBase):
    """
     Delete the dataset or change the owner and access of a Pbench dataset by modifying
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
        )

    def prepare(self, params: ApiParams, dataset: Dataset, context: ApiContext):
        """Prepare for the bulk operation

        Process and validate the API query parameters.

        Args:
            params: Type-normalized client request body JSON
            dataset: The associated Dataset object
            context: The operation's ApiContext
        """

        if context["attributes"].action != "update":
            return
        access = params.query.get("access")
        owner = params.query.get("owner")
        if not access and not owner:
            raise MissingParameters(["access", "owner"])
        if access:
            context["access"] = access
        if owner:
            authorized_user = Auth.token_auth.current_user()
            if not authorized_user.is_admin():
                raise UnauthorizedAdminAccess(authorized_user, OperationCode.UPDATE)
            context["owner"] = owner

    def generate_actions(
        self,
        dataset: Dataset,
        context: ApiContext,
        map: Iterator[IndexStream],
    ) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk update actions driven by the
        dataset document map.

        Args:
            dataset: the Dataset object
            context: CONTEXT to pass to complete
            map: Elasticsearch index document map generator

        Returns:
            A generator for Elasticsearch bulk update actions
        """
        action = context["attributes"].action
        es_doc = {}

        for field in {"access", "owner"} & set(context):
            es_doc[field] = context[field]

        # Generate a series of bulk operations, which will be passed to
        # the Elasticsearch bulk helper.
        #
        # Note that the "doc" specifies explicit instructions for updating only
        # the "access" and/or "owner" field(s) of the "authorization" subdocument:
        # no other data will be modified.

        for i in map:
            es_action = {"_op_type": action, "_index": i.index, "_id": i.id}
            if es_doc:
                es_action["doc"] = es_doc
            yield es_action

    def complete(
        self, dataset: Dataset, context: ApiContext, summary: JSONOBJECT
    ) -> None:
        """
        Complete the operation by deleting or updating the access/owner of the
        Dataset object.

        Note that an exception will be caught outside this class.

        Args:
            dataset: Dataset object
            context: CONTEXT dictionary
            summary: summary of the bulk operation
                ok: count of successful updates
                failure: count of failures
        """
        auditing: dict[str, Any] = context["auditing"]
        attributes = auditing["attributes"]
        action = context["attributes"].action
        if summary["failure"] == 0:
            if action == "update":
                access = context.get("access")
                if access:
                    attributes["access"] = access
                    dataset.access = access
                owner = context.get("owner")
                if owner:
                    attributes["owner"] = owner
                    dataset.owner_id = owner
                dataset.update()
            elif action == "delete":
                cache_m = CacheManager(self.config, current_app.logger)
                cache_m.delete(dataset.resource_id)
                dataset.delete()

                # Tell caller not to update operational state for the deleted
                # dataset.
                del context["sync"]
        else:
            context["sync"].error(
                dataset=dataset, message=f"Unable to {action} some indexed documents"
            )
