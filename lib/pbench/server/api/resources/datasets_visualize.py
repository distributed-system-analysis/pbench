from http import HTTPStatus
from urllib.request import Request

from flask import current_app, jsonify
from flask.wrappers import Response
from pquisby.lib.post_processing import BenchmarkName, InputType, QuisbyProcessing

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiBase,
    ApiContext,
    APIInternalError,
    ApiMethod,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.datasets import Metadata


class DatasetsVisualize(ApiBase):
    """
    This class implements the Server API used to retrieve data for visualization.
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True),
                ),
                authorization=ApiAuthorizationType.DATASET,
            ),
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        This function is using Quisby to process results into a form that supports visualization

        Args:
            params: includes the uri parameters, which provide the dataset.
            request: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting "NOT_FOUND" and "INTERNAL_SERVER_ERROR"

        GET /api/v1/visualize/{dataset}
        """

        dataset = params.uri["dataset"]

        metadata = Metadata.getvalue(dataset, "dataset.metalog.pbench.script")
        benchmark = metadata.upper()
        benchmark_type = BenchmarkName.__members__.get(benchmark)
        if not benchmark_type:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST, f"Unsupported Benchmark: {benchmark}"
            )

        cache_m = CacheManager(self.config, current_app.logger)
        try:
            info = cache_m.get_inventory(dataset.resource_id, "result.csv")
            file = info["stream"].read().decode("utf-8")
            info["stream"].close()
        except Exception as e:
            raise APIInternalError(str(e)) from e

        get_quisby_data = QuisbyProcessing().extract_data(
            benchmark_type, dataset.name, InputType.STREAM, file
        )

        if get_quisby_data["status"] != "success":
            raise APIInternalError(
                f"Quisby processing failure. Exception: {get_quisby_data['exception']}"
            )
        return jsonify(get_quisby_data)
