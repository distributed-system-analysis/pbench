from http import HTTPStatus
from typing import AnyStr, List, NoReturn, Optional, Union

from pbench.server import JSON, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiContext,
    ApiParams,
    ApiSchema,
    ParamType,
)
from pbench.server.api.resources.query_apis import ElasticBase
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.index_map import IndexMap
from pbench.server.database.models.templates import Template


class IndexMapBase(ElasticBase):
    """A base class for query apis that depends on the index map.

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

    def __init__(self, config: PbenchServerConfig, *schemas: ApiSchema):
        api_name = self.__class__.__name__
        for s in schemas:
            dset = s.get_param_by_type(ParamType.DATASET, ApiParams())
            assert (
                dset and dset.parameter.required
            ), f"{api_name}: dataset parameter is not defined or not required"
            assert (
                s.authorization == ApiAuthorizationType.DATASET
            ), f"{api_name}: schema authorization is not by dataset"

        super().__init__(config, *schemas)
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

    def get_index(
        self,
        dataset: Dataset,
        root_index_name: Optional[str] = None,
        ok_no_index: bool = False,
    ) -> str:
        """Retrieve ES indices based on a given root_index_name.

        Datasets without an index can't be referenced in most APIs that rely on
        Elasticsearch. Instead, we'll raise a CONFLICT error. However, the
        /api/v1/datasets API will specify ok_no_index as they need to operate
        on the dataset regardless of whether indexing is enabled.

        All indices are returned if root_index_name is omitted.

        Args:
            dataset: dataset object
            root_index_name: A root index name like "run-data"
            ok_no_index: Don't fail if dataset has no indices

        Raises:
            APIAbort(NOT_FOUND) if index is required and the dataset has none

        Returns:
            A string that joins all selected indices with ",", suitable for use
            in an Elasticsearch query URI.
        """

        index_keys = IndexMap.indices(dataset, root_index_name)
        if index_keys:
            return ",".join(index_keys)
        if ok_no_index:
            return ""

        raise APIAbort(
            HTTPStatus.NOT_FOUND,
            f"Dataset has no {root_index_name if root_index_name else 'indexed'!r} data",
        )

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
