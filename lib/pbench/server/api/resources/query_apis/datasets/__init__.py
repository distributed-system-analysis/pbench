from typing import AnyStr, List, NoReturn, Union

from pbench.server import JSON
from pbench.server.api.resources import (
    ApiAuthorizationType,
    ApiContext,
    APIInternalError,
    ApiParams,
    ApiSchema,
    ParamType,
    SchemaError,
)
from pbench.server.api.resources.query_apis import ElasticBase
from pbench.server.database.models.datasets import Dataset, Metadata, MetadataError
from pbench.server.database.models.templates import Template
from pbench.server.globals import server


class MissingDatasetNameParameter(SchemaError):
    """The subclass schema is missing the required "name" parameter required
    to locate a Dataset.

    NOTE: This is a development error, not a client error, and will be raised
    when the API is initialized at server startup. Arguably, this could be an
    assert since it prevents launching the server.
    """

    def __init__(self, subclass_name: str, message: str):
        super().__init__()
        self.subclass_name = subclass_name
        self.message = message

    def __str__(self) -> str:
        return f"API {self.subclass_name} is {self.message}"


class IndexMapBase(ElasticBase):
    """A base class for query apis that depends on Metadata for getting the
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

    def __init__(self, *schemas: ApiSchema):
        api_name = self.__class__.__name__
        assert (
            len(schemas) == 1
        ), f"{api_name}: exactly one schema required: found {len(schemas)}"
        dset = schemas[0].get_param_by_type(
            ParamType.DATASET,
            ApiParams(),
        )
        assert (
            dset and dset.parameter.required
        ), f"{api_name}: dataset parameter is not defined or not required"
        assert (
            schemas[0].authorization == ApiAuthorizationType.DATASET
        ), f"{api_name}: schema authorization is not by dataset"

        super().__init__(*schemas)
        self._method = schemas[0].method

    def preprocess(self, params: ApiParams, context: ApiContext) -> NoReturn:
        """Identify the Dataset on which we're operating, and return it in the
        context for the Elasticsearch assembly and postprocessing.

        Note that the class constructor validated that the API is authorized
        using the Dataset ownership/access, so validation and authorization has
        already taken place.
        """
        _, dataset = self.schemas.get_param_by_type(
            self._method, ParamType.DATASET, params
        )
        context["dataset"] = dataset

    def get_index(self, dataset: Dataset, root_index_name: AnyStr) -> AnyStr:
        """Retrieve the list of ES indices from the metadata table based on a
        given root_index_name.
        """
        try:
            index_map = Metadata.getvalue(dataset=dataset, key=Metadata.INDEX_MAP)
        except MetadataError as exc:
            server.logger.error("{}", exc)
            raise APIInternalError(f"Required metadata {Metadata.INDEX_MAP} missing")

        if index_map is None:
            server.logger.error("Index map metadata has no value")
            raise APIInternalError(
                f"Required metadata {Metadata.INDEX_MAP} has no value"
            )

        index_keys = [key for key in index_map if root_index_name in key]
        indices = ",".join(index_keys)
        server.logger.debug(f"Indices from metadata , {indices!r}")
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
        """Utility function to return ES mappings by querying the Template
        database against a given index.

        Args:
            document : One of the values of ES_INTERNAL_INDEX_NAMES (JSON)

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
