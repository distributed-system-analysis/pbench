from http import HTTPStatus
from urllib.request import Request

from flask import current_app
from flask.wrappers import Response
from pquisby.lib.post_processing import extract_data

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
    API class to retrieve Quisby data for a dataset
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
        This function returns the Quisby data for the requested dataset.

        Args:
            params: includes the uri parameters, which provide the dataset and target.
            request: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting either "NOT_FOUND"


        GET /api/v1/quisby/{dataset}
        """

        dataset = params.uri["dataset"]

        cache_m = CacheManager(self.config, current_app.logger)
        try:
            tarball = cache_m.find_dataset(dataset.resource_id)
        except TarballNotFound as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))

        name = Dataset.stem(tarball.tarball_path)

        try:
            file = tarball.extract(tarball.tarball_path, f"{name}/result.csv")
        except TarballUnpackError as e:
            raise APIInternalError(str(e)) from e

        json_data = extract_data("uperf",dataset.name, "localhost", "stream",file)

        if json_data["status"]=="success":
            return json_data
        else:
            raise APIInternalError("Unexpected failure from Quisby processing")

