from http import HTTPStatus
from logging import Logger

from flask import send_file
from flask.wrappers import Response

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    API_AUTHORIZATION,
    API_METHOD,
    API_OPERATION,
    ApiBase,
    ApiParams,
    ApiSchema,
    ParamType,
    Parameter,
    Schema,
)
from pbench.server.filetree import TarballNotFound, FileTree


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
                    Parameter("path", ParamType.STRING, required=False),
                ),
                authorization=API_AUTHORIZATION.DATASET,
            ),
        )

    def _get(self, params: ApiParams, _) -> Response:
        """
        This function returns the contents of the requested file as a byte stream.

        Args:
            ApiParams includes the uri parameters, which provide the dataset and path.

        Raises:
            APIAbort, reporting either "NOT_FOUND" or "UNSUPPORTED_MEDIA_TYPE"


        GET /api/v1/datasets/inventory/{dataset}/{path}
        """

        dataset = params.uri["dataset"]
        path = params.uri.get("path")

        file_tree = FileTree(self.config, self.logger)
        try:
            tarball = file_tree.find_dataset(dataset.resource_id)
        except TarballNotFound as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))

        if path is None:
            file_path = tarball.tarball_path
        else:
            dataset_location = tarball.unpacked
            if dataset_location is None:
                raise APIAbort(HTTPStatus.NOT_FOUND, "The dataset is not unpacked")
            file_path = dataset_location / path

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
