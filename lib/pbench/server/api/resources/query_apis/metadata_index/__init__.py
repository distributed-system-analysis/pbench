from http import HTTPStatus
from logging import Logger

from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    JSON,
    Schema,
)
from pbench.server.api.resources.query_apis import CONTEXT, ElasticBase
from pbench.server.database.models.datasets import Dataset, Metadata, MetadataError
from pbench.server.database.models.users import User


class MetadataBase(ElasticBase):
    """
    A base class for query apis that depends on Metadata for getting the
    indices.

    This class extends the ElasticBase class and implements a common
    `preprocess` method based on client provided run id. The subsequent methods
    such as 'assemble' and 'postprocess' need to be implemented by a respective
    subclasses.

    Note that "preprocess" provides json context containing dataset and a
    run_id that's passed to the assemble and postprocess methods.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger, schema: Schema):
        super().__init__(config, logger, schema)

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Query the Dataset associated with this run id, and determine whether the
        request is authorized for this dataset.

        If the user has authorization to read the dataset, return the Dataset
        object as CONTEXT so that the postprocess operations can use it to
        identify the index to be searched from document index metadata.
        """
        run_id = client_json.get("run_id")

        # Query the dataset using the given run id
        dataset = Dataset.query(md5=run_id)
        if not dataset:
            self.logger.error(f"Dataset with Run ID {run_id!r} not found")
            abort(HTTPStatus.NOT_FOUND, message="Dataset not found")

        owner = User.query(id=dataset.owner_id)
        if not owner:
            self.logger.error(
                f"Dataset owner ID { dataset.owner_id!r} cannot be found in Users"
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="Dataset owner not found")

        # For Iteration samples, we check authorization against the ownership of the
        # dataset that was selected rather than having an explicit "user"
        # JSON parameter. This will raise UnauthorizedAccess on failure.
        self._check_authorization(owner.username, dataset.access)

        # The dataset exists, and authenticated user has enough access so continue
        # the operation with the appropriate CONTEXT.
        return {"dataset": dataset, "run_id": run_id}

    def get_index(self, dataset, index_prefix):
        """
        Retrieve the list of ES indices from the metadata table based on a given
        index_prefix.
        """
        try:
            index_map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)
            index_keys = [key for key in index_map if index_prefix in key]
        except MetadataError as e:
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

        if len(index_keys) == 0:
            self.logger.error(
                f"Found no indices matching the prefix {index_prefix}"
                f"for a dataset {dataset!r}"
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="Found no matching indices")
        index = "".join([f"{index}," for index in index_keys])
        self.logger.debug(f"Indices from metadata , {index!r}")
        return index
