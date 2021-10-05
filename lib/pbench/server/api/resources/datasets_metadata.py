from http import HTTPStatus
from logging import Logger

from flask.json import jsonify
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
    SchemaError,
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
        Parameter("controller", ParamType.STRING, required=True),
        Parameter("name", ParamType.STRING, required=True),
        Parameter(
            "metadata",
            ParamType.LIST,
            element_type=ParamType.KEYWORD,
            keywords=ApiBase.METADATA,
        ),
    )

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

        GET /api/v1/datasets/metadata?controller=ctrl&name=dname&metadata=dashboard.seen&metadata=server.deletion
        """

        # We missed automatic schema validation due to the lack of a JSON body;
        # construct an equivalent JSON body now so we can run it through the
        # validator.
        json = {
            "controller": request.args.get("controller"),
            "name": request.args.get("name"),
            "metadata": request.args.getlist("metadata"),
        }

        # Normalize and validate the metadata keys we got via the HTTP query
        # string. These don't go through JSON schema validation, so we have
        # to do it here.
        try:
            new_json = self.GET_SCHEMA.validate(json)
        except SchemaError as e:
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

        controller = new_json.get("controller")
        name = new_json.get("name")
        keys = new_json.get("metadata")

        self.logger.info("GET metadata {} for {}>{}", keys, controller, name)
        try:
            metadata = self._get_metadata(controller, name, keys)
        except DatasetNotFound:
            abort(
                HTTPStatus.BAD_REQUEST, message=f"Dataset {controller}>{name} not found"
            )
        except MetadataError as e:
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

        return jsonify(metadata)

    def _put(self, json_data: JSON, _) -> Response:
        """
        Set or modify the values of client-accessible dataset metadata keys.

        PUT /api/v1/datasets/metadata
        {
            "controller": "ctrlname",
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
        controller = json_data["controller"]
        name = json_data["name"]
        metadata = json_data["metadata"]

        try:
            self.logger.info("PUT with {}", repr(json_data))
            dataset = Dataset.attach(controller=controller, name=name)
        except DatasetError as e:
            self.logger.warning("Dataset {}>{} not found: {}", controller, name, str(e))
            abort(
                HTTPStatus.BAD_REQUEST,
                message=f"Dataset {json_data['controller']}>{json_data['name']} not found",
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
        results = self._get_metadata(controller, name, list(metadata.keys()))
        return jsonify(results)
