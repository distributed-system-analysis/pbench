from logging import Logger
from typing import Iterator

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
from pbench.server.database.models.datasets import Dataset


class DatasetOwner(ElasticBulkBase):
    """
    Change the "owner" authorization of a Pbench dataset which is either public or
    needs change in ownership, by modifying the "authorization": {"owner": owner_id}
    subdocument of each Elasticsearch document associated with the specified dataset.

    POST /api/v1/datasets/change_owner/{dataset}?owner=user
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
                query_schema=Schema(Parameter("owner", ParamType.USER, required=True)),
                authorization=ApiAuthorizationType.ADMIN,
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

        owner_id = params.query["owner"]
        context["owner_id"] = owner_id

        self.logger.info(
            "Changing owmership operation for dataset {} to user {}", dataset, owner_id
        )

        for index, ids in map.items():
            for id in ids:
                yield {
                    "_op_type": self.action,
                    "_index": index,
                    "_id": id,
                    "doc": {"authorization": {"owner": owner_id}},
                }

    def complete(
        self, dataset: Dataset, context: ApiContext, summary: JSONOBJECT
    ) -> None:
        """
        Complete the dataset_ownership operation by updating the owner_id of the Dataset
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
        if summary["failure"] == 0:
            dataset.owner_id = context["owner_id"]
            dataset.update()
