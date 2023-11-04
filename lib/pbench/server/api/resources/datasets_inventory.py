from http import HTTPStatus
from pathlib import Path

from flask import current_app, redirect, send_file
from flask.wrappers import Request, Response

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
    CacheExtractBadPath,
    CacheManager,
    CacheType,
    TarballNotFound,
)


class DatasetsInventory(ApiBase):
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
                    Parameter("target", ParamType.STRING, required=False),
                ),
                authorization=ApiAuthorizationType.DATASET,
            ),
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """Request the contents of a results file.

        This function examines a "target" path within the results tarball of a
        dataset. If the target path is a regular file, this returns the
        contents of the requested file as a byte stream. If the target path is
        a directory, it returns a client redirect (301 status with a new url
        in the "location" header) to acquire metadata about the directory and
        its contents. Otherwise, the request fails with a BAD_REQUEST error.

        Args:
            params: includes the uri parameters, which provide the dataset and target.
            request: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting either "NOT_FOUND" or "BAD_REQUEST"

        GET /api/v1/datasets/{dataset}/inventory/{target}
        """
        dataset = params.uri["dataset"]
        target = params.uri.get("target")

        cache_m = CacheManager(self.config, current_app.logger)
        try:
            file_info = cache_m.get_inventory(dataset.resource_id, target)
        except (TarballNotFound, CacheExtractBadPath) as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))

        if file_info["type"] is CacheType.DIRECTORY:
            prefix = current_app.server_config.rest_uri
            uri = (
                f"{self._get_uri_base(request).host}{prefix}/datasets/"
                f"{dataset.resource_id}/contents/"
            )
            uri += target if target else ""
            return redirect(uri, code=HTTPStatus.MOVED_PERMANENTLY)
        elif file_info["type"] is not CacheType.FILE:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST,
                "The specified path does not refer to a regular file",
            )

        # Tell send_file to set `Content-Disposition` to "attachment" if
        # targeting the large binary tarball. Otherwise we'll recommend the
        # default "inline": only `is_file()` paths are allowed here, and
        # most are likely "displayable". While `send_file` will guess the
        # download_name from the path, setting it explicitly does no harm
        # and supports a unit test mock with no real file.
        #
        # Werkzeug will set the mime type and content encoding based on the
        # download_name suffix.
        #
        # We attach a callback to the response to close the file stream on
        # completion.
        stream = file_info["stream"]
        name = Path(file_info["name"]).name
        try:
            resp = send_file(stream, as_attachment=target is None, download_name=name)
        except Exception as e:
            if stream:
                stream.close()
            raise APIInternalError(
                f"Problem sending {dataset}:{target} stream {stream}: {str(e)!r}"
            )
        resp.call_on_close(stream.close)
        return resp
