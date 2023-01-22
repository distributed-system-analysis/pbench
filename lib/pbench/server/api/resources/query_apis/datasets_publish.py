from typing import Any, Iterator

from flask import current_app

from pbench.server import JSONOBJECT, OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    ApiAuthorizationType,
    ApiMethod,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import ApiContext, ElasticBulkBase
from pbench.server.database.models.audit import AuditType
from pbench.server.database.models.datasets import Dataset


class DatasetsPublish(ElasticBulkBase):
    """
    Change the "access" authorization of a Pbench dataset by modifying the
    "authorization": {"access": value} subdocument of each Elasticsearch
    document associated with the specified dataset.

    Called as `POST /api/v1/datasets/publish/{resource_id}?access=public`
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.POST,
                OperationCode.UPDATE,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                query_schema=Schema(
                    Parameter("access", ParamType.ACCESS, required=True),
                ),
                audit_type=AuditType.DATASET,
                audit_name="publish",
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
        access = params.query["access"]
        context["access"] = access

        current_app.logger.info("Starting publish operation for dataset {}", dataset)

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
                    "doc": {"authorization": {"access": access}},
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
        attributes["access"] = context["access"]
        if summary["failure"] == 0:
            dataset.access = context["access"]
            dataset.update()
