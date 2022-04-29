from http import HTTPStatus
from logging import Logger

from flask.json import jsonify
from flask.wrappers import Request, Response
from flask_restful import abort

from pbench.server import JSONOBJECT, PbenchServerConfig
from pbench.server.api.resources import (
    ApiBase,
    API_OPERATION,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetError,
    DatasetNotFound,
    Metadata,
    MetadataError,
)


class DatasetsMetadata(ApiBase):
    """
    API class to retrieve and mutate Dataset metadata.
    """

    GET_SCHEMA = Schema(
        Parameter("name", ParamType.STRING, required=True),
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
                Parameter("name", ParamType.STRING, required=True),
                Parameter(
                    "metadata",
                    ParamType.JSON,
                    keywords=Metadata.USER_UPDATEABLE_METADATA,
                    required=True,
                ),
            ),
            role=API_OPERATION.UPDATE,
        )

    def _get(self, _, request: Request) -> Response:
        """
        Get the values of client-accessible dataset metadata keys.

        NOTE: This does not rely on a JSON payload to identify the dataset and
        desired metadata keys. While in theory there's no restriction on
        passing a request payload to GET, the venerable (obsolete) Javascript
        requests package doesn't support it, and Elasticsearch allows POST as
        well as GET for queries because many clients can't support a payload on
        GET. In this case, we're going to experiment with an alternative, using
        query parameters.

        GET /api/v1/datasets/metadata?name=dname&metadata=dashboard.seen,server.deletion
        """

        new_json = self._validate_query_params(request, self.GET_SCHEMA)
        name = new_json.get("name")
        keys = new_json.get("metadata")

        self.logger.info("GET metadata {} for {}", keys, name)
        try:
            metadata = self._get_metadata(name, keys)
        except DatasetNotFound:
            abort(HTTPStatus.BAD_REQUEST, message=f"Dataset {name} not found")
        except MetadataError as e:
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

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
        name = json_data["name"]
        metadata = json_data["metadata"]

        try:
            self.logger.info("PUT with {}", repr(json_data))
            dataset = Dataset.query(name=name)
        except DatasetError as e:
            self.logger.warning("Dataset {} not found: {}", name, str(e))
            abort(
                HTTPStatus.BAD_REQUEST,
                message=f"Dataset {json_data['name']} not found",
            )

        failures = []
        for k, v in metadata.items():
            try:
                Metadata.setvalue(dataset, k, v)
            except MetadataError as e:
                self.logger.warning("Unable to update key {} = {!r}: {}", k, v, str(e))
                failures.append(k)
        if failures:
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                message=f"Unable to update metadata keys {','.join(failures)}",
            )
        results = self._get_metadata(name, list(metadata.keys()))
        return jsonify(results)
