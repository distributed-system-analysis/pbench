from http import HTTPStatus
from logging import Logger
from typing import Optional

from flask.json import jsonify
from flask.wrappers import Request, Response

from pbench.server import JSON, JSONOBJECT, PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.api.resources import (
    APIAbort,
    API_OPERATION,
    ApiBase,
    ParamType,
    Parameter,
    Schema,
)
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetError,
    Metadata,
    MetadataError,
)
from pbench.server.database.models.users import User


class DatasetsMetadata(ApiBase):
    """
    API class to retrieve and mutate Dataset metadata.
    """

    GET_SCHEMA = Schema(
        Parameter(
            "metadata",
            ParamType.LIST,
            element_type=ParamType.KEYWORD,
            keywords=ApiBase.METADATA,
            string_list=",",
        ),
    )

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("dataset", ParamType.STRING, required=True),
                Parameter(
                    "metadata",
                    ParamType.JSON,
                    keywords=Metadata.USER_UPDATEABLE_METADATA,
                    required=True,
                ),
            ),
            role=API_OPERATION.UPDATE,
        )

    def _get(self, json_data: JSON, request: Request) -> Response:
        """
        Get the values of client-accessible dataset metadata keys.

        Args:
            json_data: Flask's URI parameter dictionary with dataset name
            request: The original Request object containing query parameters

        GET /api/v1/datasets/metadata?name=dname&metadata=dashboard.seen,server.deletion
        """

        name = json_data.get("dataset")
        json = self._validate_query_params(request, self.GET_SCHEMA)
        keys = json.get("metadata")

        try:
            dataset = Dataset.query(name=name)
        except DatasetError:
            raise APIAbort(HTTPStatus.BAD_REQUEST, f"Dataset {name!r} not found")

        # Validate the authenticated user's authorization for the combination
        # of "owner" and "access".
        self._check_authorization(
            str(dataset.owner_id), dataset.access, check_role=API_OPERATION.READ
        )

        try:
            metadata = self._get_dataset_metadata(dataset, keys)
        except MetadataError as e:
            raise APIAbort(HTTPStatus.BAD_REQUEST, str(e))

        return jsonify(metadata)

    def _put(self, json_data: JSONOBJECT, _) -> Response:
        """
        Set or modify the values of client-accessible dataset metadata keys.

        PUT /api/v1/datasets/metadata
        {
            "name": "datasetname",
            "metadata": [
                "dashboard.seen": True,
                "user": {
                    "cloud": "AWS",
                    "contact": "john.carter@mars.org"
                }
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
            "user": {"cloud": "AWS", "contact": "json.carter@mars.org}
        ]
        """
        name = json_data["dataset"]
        metadata = json_data["metadata"]

        try:
            dataset = Dataset.query(name=name)
        except DatasetError as e:
            self.logger.warning("Dataset {!r} not found: {}", name, str(e))
            raise APIAbort(HTTPStatus.BAD_REQUEST, f"Dataset {name!r} not found")

        # Validate the authenticated user's authorization for the combination
        # of "owner" and "access".
        #
        # Note that we allow authenticated clients to set "user.*" namespace
        # metadata with READ access to the dataset because it doesn't affect
        # the Dataset itself and isn't visible to other users, but we require
        # UPDATE access for any keys outside the "user" namespace.
        role = API_OPERATION.READ
        if not Auth.token_auth.current_user():
            role = API_OPERATION.UPDATE
        else:
            for k in metadata.keys():
                if Metadata.get_native_key(k) != Metadata.USER_NATIVE_KEY:
                    role = API_OPERATION.UPDATE
        self._check_authorization(
            str(dataset.owner_id), dataset.access, check_role=role
        )

        failures = []
        for k, v in metadata.items():
            native_key = Metadata.get_native_key(k)
            user = None
            if native_key == Metadata.USER_NATIVE_KEY:
                authorized_user: Optional[User] = Auth.token_auth.current_user()
                user = authorized_user
            try:
                Metadata.setvalue(key=k, value=v, dataset=dataset, user=user)
            except MetadataError as e:
                self.logger.warning("Unable to update key {} = {!r}: {}", k, v, str(e))
                failures.append(k)
        if failures:
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
        results = self._get_dataset_metadata(dataset, list(metadata.keys()))
        return jsonify(results)
