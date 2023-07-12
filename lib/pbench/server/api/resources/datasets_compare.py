from http import HTTPStatus
from urllib.request import Request

from flask import current_app, jsonify
from flask.wrappers import Response
from pquisby.lib.post_processing import BenchmarkName, InputType, QuisbyProcessing

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorization,
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


class DatasetsCompare(ApiBase):
    """
    This class implements the Server API used to retrieve comparison data for visualization.
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                query_schema=Schema(
                    Parameter(
                        "datasets",
                        ParamType.LIST,
                        element_type=ParamType.DATASET,
                        string_list=",",
                        required=True,
                    ),
                ),
                authorization=ApiAuthorizationType.NONE,
            ),
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        This function is using Quisby to compare results into a form that supports visualization

        Args:
            params: includes the uri parameters, which provide the list of dataset.
            request: Original incoming Request object
            context: API context dictionary

        Raises:
            UnauthorizedAccess : The user isn't authorized for the requested access.
            APIAbort, reporting "NOT_FOUND" and "INTERNAL_SERVER_ERROR"
            APIInternalError, reporting the failure message

        GET /api/v1/compare?datasets=d1,d2,d3
        """

        datasets = params.query.get("datasets")
        benchmark_choice = None
        for dataset in datasets:
            benchmark = Metadata.getvalue(dataset, "dataset.metalog.pbench.script")
            # Validate if all the selected datasets is of same benchmark
            if not benchmark_choice:
                benchmark_choice = benchmark
            elif benchmark != benchmark_choice:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"Selected dataset benchmarks must match: {benchmark_choice} and {benchmark} cannot be compared.",
                )

            # Validate if the user is authorized to access the selected datasets
            self._check_authorization(
                ApiAuthorization(
                    ApiAuthorizationType.USER_ACCESS,
                    OperationCode.READ,
                    dataset.owner_id,
                    dataset.access,
                )
            )

        benchmark_type = BenchmarkName.__members__.get(benchmark.upper())
        if not benchmark_type:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST, f"Unsupported Benchmark: {benchmark}"
            )

        cache_m = CacheManager(self.config, current_app.logger)
        stream_file = {}
        for dataset in datasets:
            try:
                info = cache_m.get_inventory(dataset.resource_id, "result.csv")
                file = info["stream"].read().decode("utf-8")
                info["stream"].close()
            except Exception as e:
                raise APIInternalError(
                    f"{dataset.name} is missing 'result.csv' file"
                ) from e
            stream_file[dataset.name] = file

        quisby_response = QuisbyProcessing().compare_csv_to_json(
            benchmark_type, InputType.STREAM, stream_file
        )
        if quisby_response["status"] != "success":
            raise APIInternalError(
                f"Quisby processing failure. Exception: {quisby_response['exception']}"
            )
        quisby_response["benchmark"] = benchmark.lower()
        return jsonify(quisby_response)
