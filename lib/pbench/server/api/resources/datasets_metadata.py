from http import HTTPStatus
from logging import Logger
from typing import Optional

from flask.json import jsonify
from flask.wrappers import Request, Response

from pbench.server import PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    APIAbort,
    API_OPERATION,
    ApiBase,
    ApiParams,
    ApiSchema,
    ParamType,
    Parameter,
    Schema,
)
from pbench.server.database.models.datasets import (
    Metadata,
    MetadataError,
)
from pbench.server.database.models.users import User


class DatasetsMetadata(ApiBase):
    """
    API class to retrieve and mutate Dataset metadata.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.PUT,
                API_OPERATION.UPDATE,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                body_schema=Schema(
                    Parameter(
                        "metadata",
                        ParamType.JSON,
                        keywords=Metadata.USER_UPDATEABLE_METADATA,
                        required=True,
                        key_path=True,
                    )
                ),
                authorization=API_AUTHORIZATION.NONE,
            ),
            ApiSchema(
                API_METHOD.GET,
                API_OPERATION.READ,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                query_schema=Schema(
                    Parameter(
                        "metadata",
                        ParamType.LIST,
                        element_type=ParamType.KEYWORD,
                        keywords=Metadata.METADATA_KEYS,
                        key_path=True,
                        string_list=",",
                    )
                ),
                authorization=API_AUTHORIZATION.DATASET,
            ),
        )

    def _get(self, params: ApiParams, request: Request) -> Response:
        """
        Get the values of client-accessible dataset metadata keys.

        Args:
            params: API parameters
            request: The original Request object containing query parameters

        GET /api/v1/datasets/metadata?name=dname&metadata=dashboard.seen,server.deletion
        """

        dataset = params.uri["dataset"]
        keys = params.query.get("metadata")

        try:
            metadata = self._get_dataset_metadata(dataset, keys)
        except MetadataError as e:
            raise APIAbort(HTTPStatus.BAD_REQUEST, str(e))

        return jsonify(metadata)

    def _put(self, params: ApiParams, _) -> Response:
        """
        Set or modify the values of client-accessible dataset metadata keys.

        PUT /api/v1/datasets/metadata
        {
            "name": "datasetname",
            "metadata": [
                "dashboard.seen": True,
                "user": {"favorite": True}
            ]
        }

        Some metadata accessible via GET /api/v1/datasets/metadata (or from
        /api/v1/datasets/list and /api/v1/datasets/detail) is not modifiable by
        the client. The schema validation for PUT will fail if any of these
        keywords are specified.

        Returns the new metadata referenced in the top-level "metadata" list:
        e.g., for the above query,

        [
            "dashboard.seen": True,
            "user": {"favorite": False}
        ]
        """

        dataset = params.uri["dataset"]
        metadata = params.body["metadata"]

        # Validate the authenticated user's authorization for the combination
        # of "owner" and "access".
        #
        # The "unusual" part here is that we make a special case for
        # authenticated that are not the owner of the data: we want to allow
        # them UPDATE access to PUBLIC datasets (to which they naturally have
        # READ access) as long as they're only trying to modify a "user."
        # metadata key:
        #
        # * We want to validate authorized non-owners for READ access if
        #   they're only trying to modify "user." keys;
        # * We want to validate unauthorized users for UPDATE because they have
        #   READ access to "public" datasets but still can't write even "user."
        #   metadata;
        # * We want to validate authorized users for UPDATE if they're trying
        #   to set anything other than a "user." key because only the owner can
        #   do that...
        role = API_OPERATION.READ
        if not Auth.token_auth.current_user():
            role = API_OPERATION.UPDATE
        else:
            for k in metadata.keys():
                if Metadata.get_native_key(k) != Metadata.USER:
                    role = API_OPERATION.UPDATE
        self._check_authorization(str(dataset.owner_id), dataset.access, role)

        failures = []
        for k, v in metadata.items():
            native_key = Metadata.get_native_key(k)
            user: Optional[User] = None
            if native_key == Metadata.USER:
                user = Auth.token_auth.current_user()
            try:
                Metadata.setvalue(key=k, value=v, dataset=dataset, user=user)
            except MetadataError as e:
                self.logger.warning("Unable to update key {} = {!r}: {}", k, v, str(e))
                failures.append(k)
        if failures:
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
        results = self._get_dataset_metadata(dataset, list(metadata.keys()))
        return jsonify(results)
