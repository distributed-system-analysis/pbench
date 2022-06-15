from http import HTTPStatus
from logging import Logger
from pathlib import Path

from flask.wrappers import Request, Response
from flask import send_file

import os
from pbench.server import JSON, JSONOBJECT, PbenchServerConfig
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

from pbench.server.filetree import DatasetNotFound, FileTree


class DatasetsInventory(ApiBase):
    """
    API class to retrieve files in a byte strean of a unpacked dataset.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.GET,
                API_OPERATION.READ,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                authorization=API_AUTHORIZATION.DATASET,
            ),
        )

    def return_send_file(self, file_path):
        return send_file(file_path)

    def _get(self, params: ApiParams, request: Request) -> Response:
        """
        Get the values of client-accessible dataset and retrun the byte stream of the requested file .

        Args:
            params: Flask's URI parameter dictionary with dataset name
            request: The original Request object containing query parameters

        GET /api/v1/datasets/inventory/{dataset}/{path}
        """

        dataset = params.uri["dataset"]
        path = params.uri["path"]

        # Validate the authenticated user's authorization for the combination
        # of "owner" and "access".

        self._check_authorization(
            str(dataset.owner_id), dataset.access, API_OPERATION.READ
        )
        try:
            file_tree = FileTree(self.config, self.logger)
            dataset_location = file_tree.find_inventory(dataset.name)
            file_path = Path(os.path.join(dataset_location, Path(path)))
            if file_path.is_file():
                return self.return_send_file(file_path)
            else:
                raise APIAbort(
                    HTTPStatus.NOT_FOUND, "File is not present in the given path"
                )

        except DatasetNotFound as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))
