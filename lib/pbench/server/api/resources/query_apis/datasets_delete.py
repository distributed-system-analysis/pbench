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
from pbench.server.database.models.audit import AuditType
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.datasets import Dataset, States


class DatasetsDelete(ElasticBulkBase):
    """
    Delete the specified dataset.

    This includes all Elasticsearch documents associated with the dataset, plus
    the database representation, the tarball and MD5 file in the ARCHIVE file
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
                ApiMethod.POST,
                OperationCode.DELETE,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                audit_type=AuditType.DATASET,
                audit_name="delete",
                authorization=ApiAuthorizationType.DATASET,
            ),
            action="delete",
            require_stable=True,
        )

    def generate_actions(
        self, params: ApiParams, dataset: Dataset, context: ApiContext, map: dict[str, list[str]]
    ) -> Iterator[dict]:
        """
        Generate a series of Elasticsearch bulk delete actions driven by the
        dataset document map.

        Args:
            params: API parameters
            dataset: the Dataset object
            context: CONTEXT dictionary
            map: Elasticsearch index document map

        Returns:
            A generator for Elasticsearch bulk delete actions
        """

        dataset.advance(States.DELETING)
        self.logger.info("Starting delete operation for dataset {}", dataset)

        # Generate a series of bulk delete documents, which will be passed to
        # the Elasticsearch bulk helper.

        for index, ids in map.items():
            for id in ids:
                yield {"_op_type": self.action, "_index": index, "_id": id}

    def complete(
        self, dataset: Dataset, context: ApiContext, summary: JSONOBJECT
    ) -> None:
        """
        Complete the delete operation by deleting files (both the tarball, MD5
        file, and unpacked tarball contents) from the file system, and then
        deleting the Dataset object.

        Note that an exception will be caught outside this class; the Dataset
        object will remain to allow a retry.

        Args:
            dataset: Dataset object
            context: CONTEXT dictionary
            summary: summary of the bulk operation
                ok: count of successful updates
                failure: count of failures
        """
        # Only on total success we update the Dataset's registered access
        # column; a "partial success" will remain in the previous state.
        if summary["failure"] == 0:
            self.logger.debug("Deleting dataset {} file system representation", dataset)
            cache_m = CacheManager(self.config, self.logger)
            cache_m.delete(dataset.resource_id)
            self.logger.debug("Deleting dataset {} PostgreSQL representation", dataset)
            dataset.delete()
