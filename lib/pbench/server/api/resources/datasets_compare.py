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
from pbench.server.cache_manager import CacheManager, CacheManagerError
from pbench.server.database.models.datasets import Dataset, Metadata


class DatasetsCompare(ApiBase):
    """
    This class implements the Server API used to retrieve comparison data for visualization.
    """

    @staticmethod
    def get_benchmark_name(dataset: Dataset) -> str:
        """Convenience function to get dataset's benchmark

        The Pbench Server intake constructs a server.benchmark metadata key to
        represent the benchmark type. This helper implements a fallback for
        datasets processed prior to the implementation of server.benchmark to
        avoid null values, by using the Pbench Agent metadata.log "script"
        value if that exists and then a constant fallback value.

        TODO: This is a workaround from the transition to server.benchmark in
        order to cleanly support earlier datasets on the staging server. This
        can be removed at some point, but it's not critical.

        Args:
            dataset: Dataset object

        Returns:
            A lowercase benchmark identifer string, including the value defined
            by Metadata.SERVER_BENCHMARK_UNKNOWN if we can't find a value.
        """
        benchmark = Metadata.getvalue(dataset, Metadata.SERVER_BENCHMARK)

        if not benchmark:
            benchmark = Metadata.getvalue(dataset, "dataset.metalog.pbench.script")
            if not benchmark:
                benchmark = Metadata.SERVER_BENCHMARK_UNKNOWN
        return benchmark

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

    def _get(self, params: ApiParams, req: Request, context: ApiContext) -> Response:
        """
        This function is using Quisby to compare results into a form that supports visualization

        Args:
            params: includes the uri parameters, which provide the list of dataset.
            req: Original incoming Request object
            context: API context dictionary

        Raises:
            UnauthorizedAccess : The user isn't authorized for the requested access.
            APIAbort, reporting "NOT_FOUND" and "INTERNAL_SERVER_ERROR"
            APIInternalError, reporting the failure message

        GET /api/v1/compare?datasets=d1,d2,d3
        """

        datasets = params.query.get("datasets")
        benchmark_choice = None
        benchmark = None
        for dataset in datasets:

            # Check that the user is authorized to read each dataset
            self._check_authorization(
                ApiAuthorization(
                    ApiAuthorizationType.USER_ACCESS,
                    OperationCode.READ,
                    dataset.owner_id,
                    dataset.access,
                )
            )

            # Determine the dataset benchmark and check consistency
            benchmark = DatasetsCompare.get_benchmark_name(dataset)
            if not benchmark_choice:
                benchmark_choice = benchmark
            elif benchmark != benchmark_choice:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"Selected dataset benchmarks must match: {benchmark_choice} and {benchmark} cannot be compared.",
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
            stream_file[dataset.name] = file

        try:
            quisby_response = QuisbyProcessing().compare_csv_to_json(
                benchmark_type, InputType.STREAM, stream_file
            )
        except Exception as e:
            raise APIInternalError(f"Comparison failed with {str(e)!r}")

        if quisby_response["status"] != "success":
            raise APIInternalError(
                f"Comparison processing failure. Exception: {quisby_response['exception']}"
            )
        quisby_response["benchmark"] = benchmark
        return jsonify(quisby_response)
