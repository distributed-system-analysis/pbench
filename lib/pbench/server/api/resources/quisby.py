from http import HTTPStatus
from urllib.request import Request

from flask import current_app
from flask.wrappers import Response
from pquisby.lib.benchmarks.uperf.uperf import extract_uperf_data

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
from pbench.server.cache_manager import (
    CacheManager,
    TarballNotFound,
    TarballUnpackError,
)
from pbench.server.database import Dataset


class QuisbyData(ApiBase):
    """
    API class to retrieve inventory files from a dataset
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
        This function returns the contents of the requested file as a byte stream.

        Args:
            params: includes the uri parameters, which provide the dataset and target.
            request: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting either "NOT_FOUND" or "UNSUPPORTED_MEDIA_TYPE"


        GET /api/v1/quisby/{dataset}
        """

        dataset = params.uri["dataset"]

        cache_m = CacheManager(self.config, current_app.logger)
        try:
            tarball = cache_m.find_dataset(dataset.resource_id)
        except TarballNotFound as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))

        name = Dataset.stem(tarball.tarball_path)

        print(name)
        try:
            file = tarball.extract(tarball.tarball_path, f"{name}/result.csv")
        except TarballUnpackError as e:
            raise APIInternalError(str(e)) from e

        split_rows = file.split("\n")
        csv_data = []
        for row in split_rows:
            csv_data.append(row.split(","))

        try:
            return_val, json_data = extract_uperf_data("localhost", csv_data)
        except Exception as e:
            raise APIInternalError(str(e)) from e

        return json_data
