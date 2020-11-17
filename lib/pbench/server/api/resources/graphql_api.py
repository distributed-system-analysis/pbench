import requests
from flask_restful import Resource, abort
from flask import request, make_response
from flask_cors import cross_origin


class GraphQL(Resource):
    """GraphQL API for post request via server."""

    def __init__(self, config, logger):
        self.logger = logger
        self.graphql_host = config.get_conf(__name__, "graphql", "host", self.logger)
        self.graphql_port = config.get_conf(__name__, "graphql", "port", self.logger)

    @cross_origin()
    def post(self):
        self.graphql = f"http://{self.graphql_host}:{self.graphql_port}"

        json_data = request.get_json(silent=True)

        if not json_data:
            message = "Invalid json object"
            self.logger.warning(f"{message}: {request.url}")
            abort(400, message=message)

        try:
            # query GraphQL
            gql_response = requests.post(self.graphql, json=json_data)
            gql_response.raise_for_status()
        except requests.exceptions.ConnectionError:
            self.logger.exception("Connection refused during the GraphQL post request")
            abort(502, message="Network problem, could not post to GraphQL Endpoint")
        except requests.exceptions.Timeout:
            self.logger.exception(
                "Connection timed out during the GraphQL post request"
            )
            abort(
                504, message="Connection timed out, could not post to GraphQL Endpoint"
            )
        except Exception:
            self.logger.exception("Exception occurred during the GraphQL post request")
            abort(500, message="INTERNAL ERROR")

        try:
            # construct response object
            response = make_response(gql_response.text)
        except Exception:
            self.logger.exception("Exception occurred GraphQL response construction")
            abort(500, message="INTERNAL ERROR")

        response.status_code = gql_response.status_code
        return response
