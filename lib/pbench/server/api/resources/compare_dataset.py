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
    convert_dataset,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.cache_manager import (
    CacheManager,
    TarballNotFound,
    TarballUnpackError,
)
from pbench.server.database import Dataset


class CompareDataset(ApiBase):
    """
    API class to retrieve data using Quisby to visualize
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                query_schema=Schema(
                    Parameter(
                        "datasets", ParamType.LIST, string_list=",", required=True
                    ),
                ),
                authorization=ApiAuthorizationType.NONE,
            ),
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        This function is using Quisby to process results into a form that supports visualization

        Args:
            params: includes the uri parameters, which provide the list of dataset.
            request: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting "NOT_FOUND" and "INTERNAL_SERVER_ERROR"

        GET /api/v1/compare?datasets=d1,d2,d3
        """

        datasets = params.query.get("datasets")

        ds_list = [convert_dataset(ds, None) for ds in datasets]

        cache_m = CacheManager(self.config, current_app.logger)

        benchmark_check = []

        stream_file = {}
        for dataset in ds_list:
            metadata = self._get_dataset_metadata(
                dataset, ["dataset.metalog.pbench.script"]
            )

            benchmark = metadata["dataset.metalog.pbench.script"]
            benchmark_check.append(benchmark)

            # Validate if all the selected datasets is of same benchmark
            if len(set(benchmark_check)) != 1:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    "Requested datasets are not of same benchmark. It can't be compared",
                )

        for dataset in ds_list:
            try:
                tarball = cache_m.find_dataset(dataset.resource_id)
            except TarballNotFound as e:
                raise APIAbort(HTTPStatus.NOT_FOUND, str(e))
            name = Dataset.stem(tarball.tarball_path)
            try:
                file = tarball.extract(tarball.tarball_path, f"{name}/result.csv")
            except TarballUnpackError as e:
                raise APIInternalError(str(e)) from e
            stream_file[dataset.name] = file

        benchmark = metadata["dataset.metalog.pbench.script"].upper()
        benchmark_type = BenchmarkName.__members__.get(benchmark)
        if not benchmark_type:
            raise APIAbort(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, f"Unsupported Benchmark: {benchmark}"
            )

        get_quisby_data = QuisbyProcessing().compare_csv_to_json(
            benchmark_type, InputType.STREAM, stream_file
        )

        return jsonify(get_quisby_data)

        # if get_quisby_data["status"] == "success":
        #     return jsonify(get_quisby_data)
        #
        # else:
        #     raise APIInternalError(
        #         f"Quisby processing failure. Exception: {get_quisby_data['exception']}"
        #     )
