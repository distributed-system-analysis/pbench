import requests
from flask_restful import Resource, abort
from flask import request, make_response, jsonify
from pbench.server.api.resources.auth import auth
from pbench.server.api.resources.graphql_schema import schema


class UserMetadata(Resource):
    """
    Abstracted pbench API for handling user metadata by using graphql schema
    """

    def __init__(self, config, logger):
        self.server_config = config
        self.logger = logger

    @auth.login_required()
    def post(self):
        """
        Post request for creating metadata instance for a user.
        This requires a JWT auth token in the header field

        This requires a JSON data with required user metadata fields
        {
            "config": "config",
            "description": "description",
        }

        Required headers include
            Authorization:   JWT token (user received upon login)

        :return: JSON Payload
            response_object = {
                    "status": "success"
                    "data" {
                        "id": "metadata_id",
                        "config": "Config string"
                        "description": "Description string"
                        }
                }
        """
        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: %s", request.url)
            abort(400, message="Invalid json object in request")

        config = post_data.get("config")
        if not config:
            self.logger.warning("Config not provided during metadata creation")
            abort(400, message="Please provide a config string")

        description = post_data.get("description")
        if not description:
            self.logger.warning("Description not provided during metadata creation")
            abort(400, message="Please provide a description string")
        current_user_id = auth.current_user().id
        try:
            # query GraphQL
            query = f"""
                    mutation {{ 
                        createMetadata (input: {{config:"{config}", description:"{description}", user_id:{current_user_id}}}) {{ 
                                metadata {{
                                    id 
                                    config 
                                    description
                                    }} 
                                }} 
                        }}
                    """
            result = schema.execute(query)
        except Exception as e:
            self.logger.exception("Exception occurred during Metadata creation")
            abort(500, message="INTERNAL ERROR")
        else:
            data = result.data["createMetadata"]["metadata"]
            response_object = {
                "status": "success",
                "data": {
                    "id": data["id"],
                    "config": data["config"],
                    "description": data["description"],
                },
            }
            return make_response(jsonify(response_object), 201)


class GraphQL(Resource):
    """GraphQL API for post request via server."""

    def __init__(self, config, logger):
        self.logger = logger
        self.graphql_host = config.get_conf(__name__, "graphql", "host", self.logger)
        self.graphql_port = config.get_conf(__name__, "graphql", "port", self.logger)

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
        except requests.exceptions.HTTPError as e:
            self.logger.exception("HTTP error {} from Elasticsearch post request", e)
            abort(gql_response.status_code, message=f"HTTP error {e} from GraphQL")
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
