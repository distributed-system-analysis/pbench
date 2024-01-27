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
from pbench.server.api.resources.datasets_compare import DatasetsCompare
from pbench.server.cache_manager import CacheManager, CacheManagerError


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

    def _get(self, params: ApiParams, req: Request, context: ApiContext) -> Response:
        """
        This function is using Quisby to process results into a form that supports visualization

        Args:
            params: includes the uri parameters, which provide the dataset.
            req: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting "NOT_FOUND" and "INTERNAL_SERVER_ERROR"

        GET /api/v1/visualize/{dataset}
        """

        dataset = params.uri["dataset"]
        benchmark = DatasetsCompare.get_benchmark_name(dataset)
        benchmark_type = BenchmarkName.__members__.get(benchmark.upper())
        if not benchmark_type:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST, f"Unsupported Benchmark: {benchmark}"
            )

        cache_m = CacheManager(self.config, current_app.logger)
        try:
            file = cache_m.get_inventory_bytes(dataset.resource_id, "result.csv")
        except CacheManagerError as e:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST,
                "unable to extract postprocessed data from {dataset.name}",
            ) from e
        except Exception as e:
            raise APIInternalError(
                f"Unexpected error extracting postprocessed data from {dataset.name}"
            ) from e

        try:
            quisby_response = QuisbyProcessing().extract_data(
                benchmark_type, dataset.name, InputType.STREAM, file
            )
        except Exception as e:
            raise APIInternalError(f"Visualization failed with {str(e)!r}")

        if quisby_response["status"] != "success":
            raise APIInternalError(
                f"Visualization processing failure. Exception: {quisby_response['exception']}"
            )
        quisby_response["benchmark"] = benchmark
        return jsonify(quisby_response)
