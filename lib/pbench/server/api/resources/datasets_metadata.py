from flask.json import jsonify
from logging import Logger

from http import HTTPStatus

from flask.wrappers import Request, Response
from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    ApiBase,
    API_OPERATION,
    JSON,
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

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("controller", ParamType.STRING, required=True),
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

        GET /api/v1/datasets/metadata?controller=ctrl&name=dname&metadata=SEEN&metadata=SAVED
        """
        controller = request.args.get("controller")
        name = request.args.get("name")
        keys = request.args.getlist("metadata")
        self.logger.info("GET metadata {} for {}", name, keys)
        try:
            metadata = self._get_metadata(controller, name, keys)
        except DatasetNotFound:
            abort(HTTPStatus.BAD_REQUEST, message=f"Dataset {name} not found")
        return jsonify(metadata)

    def _put(self, json_data: JSON, _) -> Response:
        """
        Set or modify the values of client-accessible dataset metadata keys.

        PUT /api/v1/datasets/metadata
        {
            "controller": "ctrlname",
            "name": "datasetname",
            "metadata": [
                "SEEN": True,
                "USER": {
                    "cloud": "AWS",
                    "contact": "john.carter@mars.org"
                }
            ]
        }

        Some metadata accessible via GET /api/v1/datasets/metadata (or from
        /api/v1/datasets/list and /api/v1/datasets/detail) is not modifiable by
        the client, and will result in an error if specified here, including
        DELETED, OWNER, and ACCESS.
        """
        try:
            self.logger.info("PUT with {}", repr(json_data))
            dataset = Dataset.attach(
                controller=json_data["controller"], name=json_data["name"]
            )
        except DatasetError as e:
            self.logger.warning("Dataset {} not found: {}", json_data["name"], str(e))
            abort(
                HTTPStatus.BAD_REQUEST, message=f"Dataset {json_data['name']} not found"
            )
        metadata = json_data["metadata"]
        for k, v in metadata.items():
            try:
                Metadata.set(dataset, k, v)
            except MetadataError as e:
                self.logger.warning("Unable to update {} key {}: {}", k, v, str(e))
                raise
