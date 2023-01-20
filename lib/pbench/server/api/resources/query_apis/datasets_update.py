from logging import Logger
from typing import Any, Iterator

from pbench.server import JSONOBJECT, OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
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
from pbench.server.auth.auth import Auth
from pbench.server.database.models.audit import AuditType
from pbench.server.database.models.datasets import Dataset


class DatasetsUpdate(ElasticBulkBase):
    """
    Change the owner and access of a Pbench dataset by modifying the owner
     and/or access in the Dataset table and in each Elasticsearch document
    "authorization" sub-document associated with the dataset

    Called as `POST /api/v1/datasets/{resource_id}?access=public&owner=user`
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                ApiMethod.POST,
                OperationCode.UPDATE,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                query_schema=Schema(
                    Parameter("access", ParamType.ACCESS, required=False),
                    Parameter("owner", ParamType.USER, required=False),
                ),
                audit_type=AuditType.DATASET,
                audit_name="update",
                authorization=ApiAuthorizationType.DATASET,
            ),
            action="update",
            require_stable=True,
            require_map=True,
        )

    def generate_actions(
        self,
        params: ApiParams,
        dataset: Dataset,
        context: ApiContext,
        map: dict[str, list[str]],
    ) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk update actions driven by the
        dataset document map.

        Args:
            params: API parameters
            dataset: the Dataset object
            context: CONTEXT to pass to complete
            map: Elasticsearch index document map

        Returns:
            A generator for Elasticsearch bulk update actions
        """

        access = params.query.get("access")
        owner = params.query.get("owner")
        es_doc = {}
        if not access and not owner:
            raise MissingParameters(["access", "owner"])
        if access:
            context["access"] = es_doc["access"] = access
        if owner:
            authorized_user = Auth.token_auth.current_user()
            if not authorized_user.is_admin():
                raise UnauthorizedAdminAccess(authorized_user, OperationCode.UPDATE)
            context["owner"] = es_doc["owner"] = owner

        # Generate a series of bulk update documents, which will be passed to
        # the Elasticsearch bulk helper.
        #
        # Note that the "doc" specifies explicit instructions for updating only
        # the "access" field of the "authorization" subdocument: no other data
        # will be modified.
        for index, ids in map.items():
            for id in ids:
                yield {
                    "_op_type": self.action,
                    "_index": index,
                    "_id": id,
                    "doc": {"authorization": es_doc},
                }

    def complete(
        self, dataset: Dataset, context: ApiContext, summary: JSONOBJECT
    ) -> None:
        """
        Complete the publish operation by updating the access of the Dataset
        object.

        Note that an exception will be caught outside this class; the Dataset
        object will remain in the previous state to allow a retry.

        Args:
            dataset: Dataset object
            context: CONTEXT dictionary
            summary: summary of the bulk operation
                ok: count of successful updates
                failure: count of failures
        """
        auditing: dict[str, Any] = context["auditing"]
        attributes = auditing["attributes"]
        if summary["failure"] == 0:
            access = context.get("access")
            if access:
                attributes["access"] = access
                dataset.access = access
            owner = context.get("owner")
            if owner:
                attributes["owner"] = owner
                dataset.owner_id = owner
            dataset.update()
