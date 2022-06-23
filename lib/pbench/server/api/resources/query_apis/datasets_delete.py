from logging import Logger
from typing import Iterator

from pbench.server import PbenchServerConfig, JSON
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    API_OPERATION,
    ApiParams,
    ApiSchema,
    Schema,
    Parameter,
    ParamType,
)
from pbench.server.api.resources.query_apis import ElasticBulkBase
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.filetree import FileTree


class DatasetsDelete(ElasticBulkBase):
    """
    Delete the specified dataset.

    This includes all Elasticsearch documents associated with the dataset, plus
    the PostgreSQL representation, the tarball and MD5 file in the ARCHIVE file
    system tree, the unpacked tarball from the INCOMING file system tree, and the
    reference link in the RESULTS file system tree. If there is a BACKUP of the
    tarball file (which there should be, if configured), this will not touch the
    backup.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.POST,
                API_OPERATION.DELETE,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                authorization=API_AUTHORIZATION.DATASET,
            ),
            action="delete",
        )

    def generate_actions(self, params: ApiParams, dataset: Dataset) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk delete actions driven by the
        dataset document map.

        Args:
            params: API parameters
            dataset: the Dataset object

        Returns:
            A generator for Elasticsearch bulk delete actions
        """
        map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)

        self.logger.info("Starting delete operation for dataset {}", dataset)

        # Generate a series of bulk delete documents, which will be passed to
        # the Elasticsearch bulk helper.

        for index, ids in map.items():
            for id in ids:
                yield {"_op_type": self.action, "_index": index, "_id": id}

    def complete(self, dataset: Dataset, params: ApiParams, summary: JSON) -> None:
        """
        Complete the delete operation by deleting files (both the tarball, MD5
        file, and unpacked tarball contents) from the file system, and then
        deleting the Dataset object.

        Note that an exception will be caught outside this class; the Dataset
        object will remain to allow a retry.

        Args:
            dataset: Dataset object
            params: API parameters
            summary: summary of the bulk operation
                ok: count of successful updates
                failure: count of failures
        """
        # Only on total success we update the Dataset's registered access
        # column; a "partial success" will remain in the previous state.
        if summary["failure"] == 0:
            self.logger.info("Deleting dataset {} file system representation", dataset)
            file_tree = FileTree(self.config, self.logger)
            file_tree.delete(dataset.resource_id)
            self.logger.info("Deleting dataset {} PostgreSQL representation", dataset)
            dataset.delete()
