from http import HTTPStatus
from logging import Logger
from typing import AnyStr

from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import JSON, Schema, SchemaError
from pbench.server.api.resources.query_apis import CONTEXT, ElasticBase
from pbench.server.database.models.datasets import Dataset, Metadata, MetadataError
from pbench.server.database.models.users import User


class MissingRunIdSchemaParameter(SchemaError):
    """
    The subclass schema is missing the required "run_id" parameter required
    to locate a Dataset.
    """

    def __init__(self, subclass_name: str):
        super().__init__()
        self.subclass_name = subclass_name

    def __str__(self) -> str:
        return f"API {self.subclass_name} is missing schema parameter run_id"


class RunIdBase(ElasticBase):
    """
    A base class for query apis that depends on Metadata for getting the
    indices.

    This class extends the ElasticBase class and implements a common
    `preprocess` method based on client provided run id. The subsequent methods
    such as 'assemble' and 'postprocess' need to be implemented by a respective
    subclasses.

    Note that run_id is a required schema parameter for all the
    classes inheriting this class. Also "preprocess" provides json context
    containing dataset and a run_id that's passed to the assemble and
    postprocess methods.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger, schema: Schema):
        if "run_id" not in schema:
            raise MissingRunIdSchemaParameter(self.__class__.__name__)
        super().__init__(config, logger, schema)

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Query the Dataset associated with this run id, and determine whether the
        request is authorized for this dataset.

        If the user has authorization to read the dataset, return the Dataset
        object as CONTEXT so that the postprocess operations can use it to
        identify the index to be searched from document index metadata.
        """
        run_id = client_json["run_id"]

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

        # We check authorization against the ownership of the dataset that
        # was selected rather than having an explicit "user"
        # JSON parameter. This will raise UnauthorizedAccess on failure.
        self._check_authorization(owner.username, dataset.access)

        # The dataset exists, and authenticated user has enough access so continue
        # the operation with the appropriate CONTEXT.
        return {"dataset": dataset, "run_id": run_id}

    def get_index(self, dataset: Dataset, root_index_name: AnyStr) -> AnyStr:
        """
        Retrieve the list of ES indices from the metadata table based on a given
        index_prefix.
        """
        try:
            index_map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)
            index_keys = [key for key in index_map if root_index_name in key]
        except MetadataError as e:
            self.logger.error(f"Indices from metadata table not found {e!r}")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        if len(index_keys) == 0:
            self.logger.error(
                f"Found no indices matching the prefix {root_index_name}"
                f"for a dataset {dataset!r}"
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="Found no matching indices")
        index = "".join([f"{index}," for index in index_keys])
        self.logger.debug(f"Indices from metadata , {index!r}")
        return index
