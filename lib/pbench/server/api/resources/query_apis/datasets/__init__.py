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


class MissingDatasetNameParameter(SchemaError):
    """
    The subclass schema is missing the required "name" parameter required
    to locate a Dataset.

    NOTE: This is a development error, not a client error, and will be raised
    when the API is initialized at server startup. Arguably, this could be an
    assert since it prevents launching the server.
    """

    def __init__(self, subclass_name: str):
        super().__init__()
        self.subclass_name = subclass_name

    def __str__(self) -> str:
        return f"API {self.subclass_name} is missing schema parameter, name"


class IndexMapBase(ElasticBase):
    """
    A base class for query apis that depends on Metadata for getting the
    indices.

    This class extends the ElasticBase class and implements a common
    'preprocess' method which finds a target dataset by name. The ElasticBase
    methods 'assemble' and 'postprocess' must be implemented by the respective
    subclasses.

    Note that dataset 'name' is a required schema parameter for all the classes
    extending this class. The common 'preprocess' provides json context with a
    dataset that's passed to the assemble and postprocess methods.
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
        if "name" not in schema:
            raise MissingDatasetNameParameter(self.__class__.__name__)
        super().__init__(config, logger, schema)

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Query the Dataset associated with this run id, and determine whether the
        request is authorized for this dataset.

        If the user has authorization to read the dataset, return the Dataset
        object in the JSON CONTEXT so that subclass operations can use it.
        """
        dataset_name = client_json["name"]

        # Query the dataset using the given run id
        try:
            dataset = Dataset.query(name=dataset_name)
        except DatasetNotFound:
            raise APIAbort(HTTPStatus.NOT_FOUND, f"Dataset {dataset_name!r} not found.")

        # We check authorization against the ownership of the dataset that was
        # selected rather than having an explicit "user" JSON parameter. This
        # will raise UnauthorizedAccess on failure.
        self._check_authorization(str(dataset.owner_id), dataset.access)

        # The dataset exists, and the authenticated user has access, so process
        # the operation with the appropriate CONTEXT.
        return {"dataset": dataset}

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

    @staticmethod
    def get_mappings(document: JSON) -> JSON:
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
