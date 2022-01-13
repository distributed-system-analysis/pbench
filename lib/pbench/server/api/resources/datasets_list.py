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
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import (
    Dataset,
    MetadataError,
)


class DatasetsList(ApiBase):
    """
    API class to list datasets based on PostgreSQL metadata
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("name", ParamType.STRING),
                Parameter("owner", ParamType.USER),
                Parameter("access", ParamType.ACCESS),
                Parameter("controller", ParamType.STRING),
                Parameter("start", ParamType.DATE),
                Parameter("end", ParamType.DATE),
                Parameter(
                    "metadata",
                    ParamType.LIST,
                    element_type=ParamType.KEYWORD,
                    keywords=ApiBase.METADATA,
                ),
            ),
            role=API_OPERATION.READ,
        )

    def _get(self, json_data: JSON, request: Request) -> Response:
        """
        Get a list of datasets matching a set of criteria.

        NOTE: This does not rely on a JSON payload to identify the dataset and
        desired metadata keys; instead we rely on URI query parameters.

        TODO: The dispatcher is currently merging JSON request body and Flask
        URI keywords ... it probably makes sense to also merge request query
        parameters and then validate them all together; although it might make
        more sense to validate each against separate schemas.

        GET /api/v1/datasets/list?start=1970-01-01&end=2040-12-31&owner=fred&metadata=dashboard.seen&metadata=server.deletion
        """

        # We missed automatic schema validation due to the lack of a JSON body;
        # construct an equivalent JSON body now so we can run it through the
        # validator.
        json = {
            key: request.args.getlist(key)
            if self.schema[key].type == ParamType.LIST
            else request.args.get(key)
            for key in request.args.keys()
            if key in self.schema
        }

        # Normalize and validate the keys we got via the HTTP query string.
        # These aren't automatically validated by the superclass, so we
        # have to do it here.
        try:
            new_json = self.schema.validate(json)
        except SchemaError as e:
            self.logger.warning("Schema validation error {}", e)
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

        # Validate the authenticated user's authorization for the combination
        # of "owner" and "access".
        self._check_authorization(json_data.get("owner"), new_json.get("access"))

        # Build a SQLAlchemy Query object expressing all of our constraints
        #
        # TODO: Think about what other constraints we might want to support.
        # Including Metadata outside the Dataset table would be more difficult,
        # but should be possible.
        query = Database.db_session.query(Dataset)
        if "start" in new_json and "end" in new_json:
            self.logger.info("Adding start / end query")
            query = query.filter(
                Dataset.created.between(new_json["start"], new_json["end"])
            )
        elif "start" in new_json:
            self.logger.info("Adding start query")
            query = query.filter(Dataset.created >= new_json["start"])
        elif "end" in new_json:
            self.logger.info("Adding end query")
            query = query.filter(Dataset.created <= new_json["end"])
        if "name" in new_json:
            self.logger.info("Adding name query")
            query = query.filter(Dataset.name.contains(new_json["name"]))
        if "controller" in new_json:
            self.logger.info("Adding controller query")
            query = query.filter(Dataset.controller == new_json["controller"])
        query = self._build_sql_query(new_json, query)

        # Useful for debugging, but verbose: this displays the fully expanded
        # SQL `SELECT` statement.
        self.logger.debug(
            "QUERY {}", query.statement.compile(compile_kwargs={"literal_binds": True})
        )

        # Execute the filtered query, sorted by dataset name so we have a
        # consistent and reproducible output to compare.
        results = query.order_by(Dataset.name).all()

        keys = new_json.get("metadata")

        response = []
        for dataset in results:
            # TODO: Decide what we really need here for basic information. We
            # should probably drop "controller" but allow "dataset.controller"
            # metadata. We currently require "run_id" for the TOC, iteration
            # sample, and timeseries APIs, although those *should* be based on
            # dataset name. Should the output here ultimately be anything but
            # a list of matching dataset names and requested metadata for each?
            d = {
                "name": dataset.name,
                "controller": dataset.controller,
                "run_id": dataset.md5,
            }
            try:
                d["metadata"] = self._get_dataset_metadata(dataset, keys)
            except MetadataError as e:
                self.logger.warning(
                    "Error getting metadata {} for dataset {}: {}", keys, dataset, e
                )
            response.append(d)

        return jsonify(response)
