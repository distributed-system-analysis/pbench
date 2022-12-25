from http import HTTPStatus
from urllib.request import Request

from flask import send_file
from flask.wrappers import Response

from pbench.server import OperationCode
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiBase,
    ApiContext,
    ApiMethod,
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

    endpoint = "datasets_inventory"
    urls = [
        "datasets/inventory/<string:dataset>",
        "datasets/inventory/<string:dataset>/",
        "datasets/inventory/<string:dataset>/<path:target>",
    ]

    def __init__(self):
        schema_kwargs = dict(
            uri_schema=Schema(
                Parameter("dataset", ParamType.DATASET, required=True),
                Parameter("target", ParamType.STRING, required=False),
            ),
            authorization=ApiAuthorizationType.DATASET,
        )
        super().__init__(
            ApiSchema(ApiMethod.GET, OperationCode.READ, **schema_kwargs),
            ApiSchema(ApiMethod.HEAD, OperationCode.READ, **schema_kwargs),
        )

    def _base_get(self, params: ApiParams, do_sendfile: bool = True) -> Response:

        dataset = params.uri["dataset"]
        target = params.uri.get("target")

        cache_m = CacheManager()
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
            if do_sendfile:
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

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """This function returns the contents of the requested file as a byte stream.

        Args:
            params: includes the uri parameters, which provide the dataset and target.
            request: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting either "NOT_FOUND" or "UNSUPPORTED_MEDIA_TYPE"


        GET /api/v1/datasets/inventory/{dataset}/{target}
        """
        return self._base_get(params)

    def _head(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """Behaves exactly the same as `_get` but does not send the file contents."""
        return self._base_get(params, do_sendfile=False)
