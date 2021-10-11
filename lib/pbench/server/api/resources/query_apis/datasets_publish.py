from logging import Logger
from typing import Iterator

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    API_OPERATION,
    JSON,
    Schema,
    Parameter,
    ParamType
)
from pbench.server.api.resources.query_apis import ElasticBulkBase
from pbench.server.database.models.datasets import Dataset, Metadata


class DatasetsPublish(ElasticBulkBase):
    """
    Change the "access" authorization of a Pbench dataset
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

    def generate_documents(self, json_data: JSON, dataset: Dataset) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk update operation documents
        driven by the dataset document map.

        {
            "_op_type": "update",
            "_index": index_name,
            "_id": document_id,
            "doc": {"authorization": {"access": new_access}}
        }

        json_data: JSON dictionary of type-normalized key-value pairs
            controller: the controller that generated the dataset
            name: name of the dataset to publish
            access: The desired access level of the dataset

        context: A dict containing a "dataset" key with the Dataset
            object, which contains the root run-data index document ID.
        """
        name = json_data["name"]
        access = json_data["access"]
        user = dataset.owner

        self.logger.info(
            "Update access for dataset {} for user {} to {}",
            name,
            user,
            access
        )

        map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)
        doc_count = sum(len(i) for i in map.values())

        self.logger.info(
            "Publish operation will update {} Elasticsearch documents in {} indices: {}",
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
                    "doc": {"authorization": {"access": access}}
                }

    def complete(self, dataset: Dataset, json_data: JSON, error_count: int) -> None:
        # Only on total success we update the Dataset's registered access
        # column; a "partial success" will remain in the previous state.
        if error_count == 0:
            dataset.access = json_data["access"]
            dataset.update()
