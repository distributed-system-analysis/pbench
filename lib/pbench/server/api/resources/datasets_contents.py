from http import HTTPStatus

from flask import current_app, jsonify
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
    BadDirpath,
    CacheExtractBadPath,
    CacheManager,
    TarballNotFound,
)
from pbench.server.database.models.datasets import Dataset


class DatasetsContents(ApiBase):
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

    def _get(self, params: ApiParams, req: Request, context: ApiContext) -> Response:
        """
        Returns metadata about the target file path within a tarball.

        Args:
            params: includes the uri parameters, which provide the dataset and target.
            req: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting either "NOT_FOUND" or "UNSUPPORTED_MEDIA_TYPE"

        GET /api/v1/datasets/{dataset}/contents/{target}
        """

        dataset: Dataset = params.uri["dataset"]
        target = params.uri.get("target")
        path = "." if target in ("/", None) else target

        prefix = current_app.server_config.rest_uri
        origin = (
            f"{self._get_uri_base(req).host}{prefix}/datasets/{dataset.resource_id}"
        )

        cache_m = CacheManager(self.config, current_app.logger)
        try:
            info = cache_m.get_contents(dataset.resource_id, path, origin)
        except (BadDirpath, CacheExtractBadPath, TarballNotFound) as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))
        except Exception as e:
            raise APIInternalError(f"Cache find error: {str(e)!r}")

        try:
            return jsonify(info)
        except Exception as e:
            raise APIInternalError(f"JSONIFY {info}: {str(e)!r}")
