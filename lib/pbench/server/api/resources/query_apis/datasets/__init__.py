from http import HTTPStatus
from logging import Logger
from typing import AnyStr, Union, List

from pbench.server import PbenchServerConfig, JSON
from pbench.server.api.resources import APIAbort, Schema, SchemaError

from pbench.server.api.resources.query_apis import CONTEXT, ElasticBase
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetNotFound,
    Metadata,
    MetadataError,
)
from pbench.server.database.models.template import Template
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

    # Mapping for client friendly ES index names and ES internal index names
    ES_INTERNAL_INDEX_NAMES = {
        "iterations": {
            "index": "result-data-sample",
            "whitelist": ["run", "sample", "iteration", "benchmark"],
        },
        "timeseries": {
            "index": "result-data",
            "whitelist": [
                "@timestamp",
                "@timestamp_original",
                "result_data_sample_parent",
                "run",
                "iteration",
                "sample",
                "result",
            ],
        },
        "summary": {
            "index": "run",
            "whitelist": [
                "@timestamp",
                "@metadata",
                "host_tools_info",
                "run",
                "sosreports",
            ],
        },
        "contents": {"index": "run-toc", "whitelist": ["directory", "files"]},
    }

    def __init__(self, config: PbenchServerConfig, logger: Logger, schema: Schema):
        if "run_id" not in schema:
            raise MissingRunIdSchemaParameter(self.__class__.__name__)
        super().__init__(config, logger, schema)

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Query the Dataset associated with this run id, and determine whether the
        request is authorized for this dataset.

        If the user has authorization to read the dataset, return the Dataset
        object and run_id as JSON CONTEXT so that the postprocess operations
        can use it to identify the index to be searched from document index
        metadata.

        Raises:
        APIAbort: input can't be validated or normalized
        """
        run_id = client_json["run_id"]

        # Query the dataset using the given run id
        try:
            dataset = Dataset.query(md5=run_id)
        except DatasetNotFound:
            raise APIAbort(
                HTTPStatus.NOT_FOUND, f"No datasets with Run ID '{run_id!r}' found."
            )
        owner = User.query(id=dataset.owner_id)
        if not owner:
            self.logger.error(
                f"Dataset owner ID { dataset.owner_id!r} cannot be found in Users"
            )
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
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
        root_index_name.
        """
        try:
            index_map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)
        except MetadataError as exc:
            self.logger.error("{}", str(exc))
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)

        if index_map is None:
            self.logger.error("Index map metadata has no value")
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)

        index_keys = [key for key in index_map if root_index_name in key]
        indices = ",".join(index_keys)
        self.logger.debug(f"Indices from metadata , {indices!r}")
        return indices

    def get_aggregatable_fields(
        self, mappings: JSON, prefix: AnyStr = "", result: Union[List, None] = None
    ) -> List:
        if result is None:
            result = []
        if "properties" in mappings:
            for p, m in mappings["properties"].items():
                self.get_aggregatable_fields(m, f"{prefix}{p}.", result)
        elif mappings.get("type") != "text":
            result.append(prefix[:-1])  # Remove the trailing dot, if any
        else:
            for f, v in mappings.get("fields", {}).items():
                self.get_aggregatable_fields(v, f"{prefix}{f}.", result)
        return result

    def get_mappings(self, document: JSON) -> JSON:
        """
        Utility function to return ES mappings by querying the Template
        database against a given index.

        Args:
            document: One of the values of ES_INTERNAL_INDEX_NAMES (JSON)
        Returns:
            JSON containing whitelisted keys of the index and corresponding
            values.
        """
        template = Template.find(document["index"])

        # Only keep the whitelisted fields
        return {
            "properties": {
                key: value
                for key, value in template.mappings["properties"].items()
                if key in document["whitelist"]
            }
        }
