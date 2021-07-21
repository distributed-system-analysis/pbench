from http import HTTPStatus
from logging import Logger
from typing import Any, AnyStr, Dict

from flask import jsonify
from flask_restful import Resource, abort

from pbench.server.database.models.template import Template, TemplateNotFound


class IndexMappings(Resource):
    """
    Get properties of the run-data document type on which the dashboard can search.
    This API currently only returns mapping properties of run-data documents.

    TODO: In future we can tweak this API to take the document type name from the user
    and query that type name against the template table to return the appropriate mappings

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

    def __init__(self, logger: Logger):
        self.logger = logger

    def get(self, index_name: AnyStr) -> Dict[AnyStr, Any]:
        """
        Return mapping properties of the document specified by the index name in the URI.
        For example, user can get the run document properties by making a GET request on
        index/mappings/run. Similarly other index documents can be fetched by making a GET
        request on appropriate index names.
        We fetch the mapping by querying the template database. If the template is not found
        in the database NOT_FOUND error will be raised.
        """
        try:
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
            abort(HTTPStatus.NOT_FOUND, message="Mapping not found")
