from logging import Logger
from typing import Iterator

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    API_OPERATION,
    JSON,
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
            Schema(
                Parameter("controller", ParamType.STRING, required=True),
                Parameter("name", ParamType.STRING, required=True),
                Parameter("access", ParamType.ACCESS, required=True),
            ),
            role=API_OPERATION.UPDATE,
        )

    def generate_actions(self, json_data: JSON, dataset: Dataset) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk update actions driven by the
        dataset document map.

        Args:
            json_data: Type-normalized client JSON input
                access: The desired access level of the dataset
            dataset: the Dataset object

        Returns:
            A sequence of Elasticsearch bulk actions
        """
        access = json_data["access"]
        map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)
        doc_count = sum(len(i) for i in map.values())

        self.logger.info(
            "Publish operation for dataset {} will update {} Elasticsearch documents in {} indices: {}",
            dataset,
            doc_count,
            len(map),
            list(map.keys()),
        )

        # Generate a series of bulk update documents, which will be passed to
        # the Elasticsearch bulk helper

        for index, ids in map.items():
            for id in ids:
                yield {
                    "_op_type": "update",
                    "_index": index,
                    "_id": id,
                    "doc": {"authorization": {"access": access}},
                }

    def complete(self, dataset: Dataset, json_data: JSON, summary: JSON) -> None:
        # Only on total success we update the Dataset's registered access
        # column; a "partial success" will remain in the previous state.
        if summary["failure"] == 0:
            dataset.access = json_data["access"]
            dataset.update()
