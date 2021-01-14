import requests
import datetime
import json
from flask_restful import Resource, abort
from flask import request, make_response, jsonify
from pbench.server.api.resources.auth import auth
from pbench.server.api.resources.models import MetadataModel
from pbench.server.api.resources.database import Database


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
            # Create a new metadata session
            metadata_session = MetadataModel(
                created=str(datetime.datetime.now()),
                config=config,
                description=description,
                user_id=current_user_id
            )
            # insert the metadata session for a user
            Database.db_session.add(metadata_session)
            Database.db_session.commit()
            self.logger.info("New user metadata session created")
        except Exception:
            self.logger.exception("Exception occurred during Metadata creation")
            abort(500, message="INTERNAL ERROR")
        else:
            response_object = {
                "status": "success",
                "data": {
                    "id": metadata_session.id,
                    "config": metadata_session.config,
                    "description": metadata_session.description,
                },
            }
            return make_response(jsonify(response_object), 201)

    @auth.login_required()
    def get(self):
        """
        Get request for querying all the metadata sessions for a user.
        This requires a JWT auth token in the header field

        Required headers include
            Authorization:   JWT token (user received upon login)

        :return: JSON Payload
            response_object = {
                    "status": "success"
                    "data": {
                        "sessions": [
                            {"id": "metadata_id",
                            "config": "Config string"
                            "description": "Description string"},
                            {}]
                        }
                }
        """
        current_user_id = auth.current_user().id
        try:
            # Fetch the metadata session
            sessions = (
                Database.db_session.query(MetadataModel)
                .filter_by(user_id=current_user_id)
                .all()
            )

            req_keys = ["id", "config", "description", "created"]
            data = json.dumps([{key: session.as_dict()[key] for key in req_keys} for session in sessions])
        except Exception:
            self.logger.exception("Exception occurred during querying Metadata model")
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "status": "success",
            "data": {
                "sessions": data
            },
        }
        return make_response(jsonify(response_object), 200)


class QueryMetadata(Resource):
    """
    Abstracted pbench API for querying a single user metadata session
    """

    def __init__(self, config, logger):
        self.server_config = config
        self.logger = logger

    @auth.login_required()
    def get(self, id=None):
        """
        Get request for querying a metadata session for a user given a metadata id.
        This requires a JWT auth token in the header field

        This requires a JSON data with required user metadata fields to update
        {
            "description": "description",
        }

        The url requires a metadata session id such as /user/metadata/<string:id>

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
        if not id:
            self.logger.warning("Meatadata id not provided during metadata query")
            abort(400, message="Please provide a metadata id to query")

        try:
            # Fetch the metadata session
            session = (
                Database.db_session.query(MetadataModel)
                .filter_by(id=id)
                .first()
            )
        except Exception:
            self.logger.exception("Exception occurred during querying Metadata model")
            abort(500, message="INTERNAL ERROR")
        else:
            response_object = {
                "status": "success",
                "data": {
                    "id": session.id,
                    "config": session.config,
                    "description": session.description,
                },
            }
            return make_response(jsonify(response_object), 200)

    @auth.login_required()
    def put(self, id=None):
        """
        Put request for updating a metadata session for a user given a metadata id.
        This requires a JWT auth token in the header field

        The url requires a metadata session id such as /user/metadata/<string:id>

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
        if not id:
            self.logger.warning("Meatadata id not provided during metadata query")
            abort(400, message="Please provide a metadata id to query")

        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: %s", request.url)
            abort(400, message="Invalid json object in request")

        description = post_data.get("description")
        if not description:
            self.logger.warning("Description not provided during metadata update")
            abort(400, message="Please provide a description string")

        try:
            # Fetch the metadata session
            session = (
                Database.db_session.query(MetadataModel)
                .filter_by(id=id)
                .first()
            )
            session.description = description
            # Update the metadata session for a user
            Database.db_session.add(session)
            Database.db_session.commit()
            self.logger.info("User metadata session updated")
        except Exception:
            self.logger.exception("Exception occurred during querying Metadata model")
            abort(500, message="INTERNAL ERROR")
        else:
            response_object = {
                "status": "success",
                "data": {
                    "id": session.id,
                    "config": session.config,
                    "description": session.description,
                },
            }
            return make_response(jsonify(response_object), 200)


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
