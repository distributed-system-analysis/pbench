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
        path = Path("." if target in ("/", None) else target)

        cache_m = CacheManager(self.config, current_app.logger)
        try:
            info = cache_m.find_entry(dataset.resource_id, path)
        except (BadDirpath, CacheExtractBadPath, TarballNotFound) as e:
            raise APIAbort(HTTPStatus.NOT_FOUND, str(e))
        except Exception as e:
            raise APIInternalError(f"Cache find error: {str(e)!r}")

        prefix = current_app.server_config.rest_uri
        origin = (
            f"{self._get_uri_base(request).host}{prefix}/datasets/{dataset.resource_id}"
        )

        details: CacheObject = info["details"]
        if details.type is CacheType.DIRECTORY:
            children = info["children"] if "children" in info else {}
            dir_list = []
            file_list = []

            for c, value in children.items():
                d: CacheObject = value["details"]
                if d.type is CacheType.DIRECTORY:
                    dir_list.append(
                        {
                            "name": c,
                            "type": d.type.name,
                            "uri": f"{origin}/contents/{d.location}",
                        }
                    )
                elif d.type is CacheType.SYMLINK:
                    if d.resolve_type is CacheType.DIRECTORY:
                        uri = f"{origin}/contents/{d.resolve_path}"
                    elif d.resolve_type is CacheType.FILE:
                        uri = f"{origin}/inventory/{d.resolve_path}"
                    else:
                        uri = f"{origin}/inventory/{d.location}"
                    file_list.append(
                        {
                            "name": c,
                            "type": d.type.name,
                            "link": str(d.resolve_path),
                            "link_type": d.resolve_type.name,
                            "uri": uri,
                        }
                    )
                else:
                    r = {
                        "name": c,
                        "type": d.type.name,
                        "uri": f"{origin}/inventory/{d.location}",
                    }
                    if d.type is CacheType.FILE:
                        r["size"] = d.size
                    file_list.append(r)

            dir_list.sort(key=lambda d: d["name"])
            file_list.sort(key=lambda d: d["name"])

            # Normalize because we want the "root" directory to be reported as
            # "" rather than as Path's favored "."
            loc = str(details.location)
            name = details.name
            if loc == ".":
                loc = ""
                name = ""
            val = {
                "name": name,
                "type": details.type.name,
                "directories": dir_list,
                "files": file_list,
                "uri": f"{origin}/contents/{loc}",
            }
        else:
            access = "inventory"
            link = str(details.location)
            if details.type is CacheType.SYMLINK:
                link = str(details.resolve_path)
                if details.resolve_type is CacheType.DIRECTORY:
                    access = "contents"
                elif details.resolve_type is not CacheType.FILE:
                    link = str(details.location)
            else:
                link = str(details.location)
            val = {
                "name": details.name,
                "type": details.type.name,
                "uri": f"{origin}/{access}/{link}",
            }
            if details.type is CacheType.SYMLINK:
                val["link"] = link
                val["link_type"] = details.resolve_type.name
            elif details.type is CacheType.FILE:
                val["size"] = details.size

        try:
            return jsonify(val)
        except Exception as e:
            raise APIInternalError(f"JSONIFY {val}: {str(e)!r}")
