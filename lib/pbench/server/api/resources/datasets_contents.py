from http import HTTPStatus
from pathlib import Path

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
    CacheObject,
    CacheType,
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

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Returns metadata about the target file path within a tarball.

        Args:
            params: includes the uri parameters, which provide the dataset and target.
            request: Original incoming Request object
            context: API context dictionary

        Raises:
            APIAbort, reporting either "NOT_FOUND" or "UNSUPPORTED_MEDIA_TYPE"

        GET /api/v1/datasets/{dataset}/contents/{target}
        """

        dataset: Dataset = params.uri["dataset"]
        target = params.uri.get("target")
        path = Path("" if target in ("/", None) else target)

        cache_m = CacheManager(self.config, current_app.logger)
        try:
            info = cache_m.find_entry(dataset.resource_id, path)
        except (BadDirpath, CacheExtractBadPath, TarballNotFound) as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))
        except Exception as e:
            raise APIInternalError(str(e))

        prefix = current_app.server_config.rest_uri
        origin = (
            f"{self._get_uri_base(request).host}{prefix}/datasets/{dataset.resource_id}"
        )

        details: CacheObject = info["details"]
        current_app.logger.info(
            "{!r} -> {{name: {!r}, loc: {!r}}}",
            str(path),
            details.name,
            str(details.location),
        )
        if details.type is CacheType.DIRECTORY:
            children = info["children"] if "children" in info else {}
            dir_list = []
            file_list = []

            for c, value in children.items():
                d: CacheObject = value["details"]
                if d.type == CacheType.DIRECTORY:
                    dir_list.append(
                        {
                            "name": c,
                            "type": d.type.name,
                            "uri": f"{origin}/contents/{d.location}",
                        }
                    )
                elif d.type == CacheType.FILE:
                    file_list.append(
                        {
                            "name": c,
                            "size": d.size,
                            "type": d.type.name,
                            "uri": f"{origin}/inventory/{d.location}",
                        }
                    )

            dir_list.sort(key=lambda d: d["name"])
            file_list.sort(key=lambda d: d["name"])

            # Normalize because we want the "root" directory to be reported as
            # "" rather than as Path's favored "."
            loc = "" if str(details.location) == "." else str(details.location)
            val = {
                "name": details.name,
                "type": details.type.name,
                "directories": dir_list,
                "files": file_list,
                "uri": f"{origin}/contents/{loc}",
            }
        else:
            val = {
                "name": details.name,
                "size": details.size,
                "type": details.type.name,
                "uri": f"{origin}/inventory/{details.location}",
            }

        try:
            return jsonify(val)
        except Exception as e:
            raise APIInternalError(str(e))
