from http import HTTPStatus
from logging import Logger

from flask.json import jsonify
from flask.wrappers import Request, Response

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorization,
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
from pbench.server.auth.auth import Auth, get_current_user_id
from pbench.server.database.models.audit import AuditType
from pbench.server.database.models.datasets import (
    Metadata,
    MetadataBadValue,
    MetadataError,
)


class DatasetsMetadata(ApiBase):
    """
    API class to retrieve and mutate Dataset metadata.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                ApiMethod.PUT,
                OperationCode.UPDATE,
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
                audit_type=AuditType.DATASET,
                audit_name="metadata",
                authorization=ApiAuthorizationType.NONE,
            ),
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
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
                authorization=ApiAuthorizationType.DATASET,
            ),
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Get the values of client-accessible dataset metadata keys.

        Args:
            params: API parameters
            request: The original Request object containing query parameters
            context: API context dictionary

        GET /api/v1/datasets/metadata?name=dname&metadata=global.seen,server.deletion
        """

        dataset = params.uri["dataset"]
        keys = params.query.get("metadata")

        try:
            metadata = self._get_dataset_metadata(dataset, keys)
        except MetadataError as e:
            raise APIAbort(HTTPStatus.BAD_REQUEST, str(e))

        return jsonify(metadata)

    def _put(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Set or modify the values of client-accessible dataset metadata keys.

        Args:
            params: API parameters
            request: The original Request object containing query parameters
            context: API context dictionary

        PUT /api/v1/datasets/metadata
        {
            "name": "datasetname",
            "metadata": [
                "global.seen": True,
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
            "global.seen": True,
            "user": {"favorite": False}
        ]
        """

        dataset = params.uri["dataset"]
        metadata = params.body["metadata"]

        context["auditing"]["attributes"] = {"updated": metadata}

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
        role = OperationCode.READ
        if not Auth.token_auth.current_user():
            role = OperationCode.UPDATE
        else:
            for k in metadata.keys():
                if Metadata.get_native_key(k) != Metadata.USER:
                    role = OperationCode.UPDATE
        self._check_authorization(
            ApiAuthorization(
                ApiAuthorizationType.USER_ACCESS,
                role,
                str(dataset.owner_id),
                dataset.access,
            )
        )

        # Validate the metadata key values in a separate pass so that we can
        # fail before committing any changes to the database.
        failures = []
        for k, v in metadata.items():
            try:
                Metadata.validate(dataset=dataset, key=k, value=v)
            except MetadataBadValue as e:
                failures.append(str(e))

        if failures:
            raise APIAbort(HTTPStatus.BAD_REQUEST, ", ".join(failures))

        # Now update the metadata, which may occur in multiple SQL operations
        # across namespaces. Make a best attempt to update all even if we
        # encounter an unexpected error.
        fail = False
        for k, v in metadata.items():
            native_key = Metadata.get_native_key(k)
            user_id = None
            if native_key == Metadata.USER:
                user_id = get_current_user_id()
            try:
                Metadata.setvalue(key=k, value=v, dataset=dataset, user_id=user_id)
            except MetadataError as e:
                self.logger.warning("Unable to update key {} = {!r}: {}", k, v, str(e))
                fail = True

        if fail:
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
        results = self._get_dataset_metadata(dataset, list(metadata.keys()))
        return jsonify(results)
