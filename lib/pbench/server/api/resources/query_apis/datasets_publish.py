from logging import Logger
from typing import Iterator

from pbench.server import PbenchServerConfig, JSON
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    API_OPERATION,
    ApiSchema,
    Schema,
    Parameter,
    ParamType,
)
from pbench.server.api.resources.query_apis import ElasticBulkBase
from pbench.server.database.models.datasets import Dataset, Metadata


class DatasetsPublish(ElasticBulkBase):
    """
    Change the "access" authorization of a Pbench dataset by modifying the
    "authorization": {"access": value} subdocument of each Elasticsearch
    document associated with the specified dataset.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.POST,
                API_OPERATION.UPDATE,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                body_schema=Schema(
                    Parameter("access", ParamType.ACCESS, required=True),
                ),
                authorization=API_AUTHORIZATION.DATASET,
            ),
            action="update",
        )

    def generate_actions(self, params: JSON, dataset: Dataset) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk update actions driven by the
        dataset document map.

        Args:
            params: API request body parameters
            dataset: the Dataset object

        Returns:
            A generator for Elasticsearch bulk update actions
        """
        access = params["access"]
        map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)

        self.logger.info("Starting publish operation for dataset {}", dataset)

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

    def complete(self, dataset: Dataset, params: JSON, summary: JSON) -> None:
        """
        Complete the publish operation by updating the access of the Dataset
        object.

        Note that an exception will be caught outside this class; the Dataset
        object will remain in the previous state to allow a retry.

        Args:
            dataset: Dataset object
            params: API parameters
            summary: summary of the bulk operation
                ok: count of successful updates
                failure: count of failures
        """
        if summary["failure"] == 0:
            dataset.access = params["access"]
            dataset.update()
