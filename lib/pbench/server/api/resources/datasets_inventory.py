from http import HTTPStatus
from logging import Logger

from flask import send_file
from flask.wrappers import Response

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    API_OPERATION,
    APIAbort,
    ApiBase,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.cache_manager import CacheManager, TarballNotFound


class DatasetsInventory(ApiBase):
    """
    API class to retrieve inventory files from a dataset
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.GET,
                API_OPERATION.READ,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True),
                    Parameter("target", ParamType.STRING, required=False),
                ),
                authorization=API_AUTHORIZATION.DATASET,
            ),
        )

    def _get(self, params: ApiParams, _) -> Response:
        """
        This function returns the contents of the requested file as a byte stream.

        Args:
            ApiParams includes the uri parameters, which provide the dataset and target.

        Raises:
            APIAbort, reporting either "NOT_FOUND" or "UNSUPPORTED_MEDIA_TYPE"


        GET /api/v1/datasets/inventory/{dataset}/{target}
        """

        dataset = params.uri["dataset"]
        target = params.uri.get("target")

        cache_m = CacheManager(self.config, self.logger)
        try:
            tarball = cache_m.find_dataset(dataset.resource_id)
        except TarballNotFound as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))

        if target is None:
            file_path = tarball.tarball_path
        else:
            dataset_location = tarball.unpacked
            if dataset_location is None:
                raise APIAbort(HTTPStatus.NOT_FOUND, "The dataset is not unpacked")
            file_path = dataset_location / target

        if file_path.is_file():
            return send_file(file_path)
        elif file_path.exists():
            raise APIAbort(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "The specified path does not refer to a regular file",
            )
        else:
            raise APIAbort(
                HTTPStatus.NOT_FOUND, "The specified path does not refer to a file"
            )
