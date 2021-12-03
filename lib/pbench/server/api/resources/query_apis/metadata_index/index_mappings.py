from http import HTTPStatus
from logging import Logger
from typing import Any, AnyStr, Dict

from flask import jsonify
from flask.wrappers import Request
from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    ApiBase,
    Schema,
    Parameter,
    ParamType,
    SchemaError,
)

from pbench.server.api.resources.query_apis.metadata_index import RunIdBase
from pbench.server.database.models.template import Template, TemplateNotFound


class IndexMappings(ApiBase):
    """
    Get properties of a document on which the client can search.
    This API currently only supports mapping properties of documents specified
    in RunIdBase.ES_INTERNAL_INDEX_NAMES.

    Example: get /api/v1/index/mappings/search
    :return:
    {
        "@metadata":
            [
                "controller_dir",
                "file-date",
                "file-name",
                "file-size",
                "md5",
                ...
            ],
       "host_tools_info":
            [
                "hostname",
                "hostname-f",
                ...
            ],
        "authorization":
            [
                "access",
                "owner"
            ]
        "run":
            [
                "id",
                "controller",
                "user",
                "name",
                ...
            ],
        "sosreports":
            [
                "hostname-f",
                "sosreport-error",
                "hostname-s",
                ...
            ]
    }
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter(
                    "index_key",
                    ParamType.KEYWORD,
                    required=True,
                    keywords=list(RunIdBase.ES_INTERNAL_INDEX_NAMES.keys()),
                    uri_parameter=True,
                )
            ),
        )

    def _get(self, index_key: AnyStr, request: Request) -> Dict[AnyStr, Any]:
        """
        Return mapping properties of the document specified by the index key
        in the URI (supported index keys are defined in RunIdBase.ES_INTERNAL_INDEX_NAMES).
        For example, user can get the run document properties by making a GET
        request on index/mappings/search. Similarly other index documents can be
        fetched by making a GET request on appropriate index names.

        The mappings are retrieved by querying the template database.
        """
        # Normalize and validate the index keys we got via URI string. These
        # don't go through JSON schema validation, so we have
        # to do it here.
        try:
            self.schema.validate(index_key)
        except SchemaError as e:
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

        index = RunIdBase.ES_INTERNAL_INDEX_NAMES[index_key["index_key"]]
        try:
            index_name = index["index"]
            template = Template.find(index_name)
            mappings = template.mappings

            result = {}
            for property in mappings["properties"]:
                if "properties" in mappings["properties"][property]:
                    result[property] = list(
                        mappings["properties"][property]["properties"].keys()
                    )

            # construct response object
            return jsonify(result)
        except TemplateNotFound:
            self.logger.exception(
                "Document template {} not found in the database.", index_name
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
