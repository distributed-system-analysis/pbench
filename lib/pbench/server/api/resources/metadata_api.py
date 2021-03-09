from flask_restful import Resource, abort
from flask import request, make_response, jsonify
from pbench.server.database.models.metadata import Metadata
from pbench.server.api.auth import Auth


class UserMetadata(Resource):
    """
    Abstracted pbench API for handling user metadata by using graphql schema
    """

    def __init__(self, config, logger, auth):
        self.server_config = config
        self.logger = logger
        self.auth = auth

    @Auth.token_auth.login_required()
    def post(self):
        """
        Post request for creating metadata instance for a user.
        This requires a Pbench auth token in the header field

        This requires a JSON data with required user metadata fields
        {
            "config": "config",
            "description": "description",
        }

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "success"
                    "data" {
                        "id": "metadata_id",
                        "config": "Config string"
                        "description": "Description string"
                        }
                }
        """
        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        current_user_id = self.auth.token_auth.current_user().id

        config = post_data.get("config")
        if not config:
            self.logger.warning(
                "Config not provided during metadata creation. user_id: {}",
                current_user_id,
            )
            abort(400, message="Config field missing")

        description = post_data.get("description")
        if not description:
            self.logger.warning(
                "Description not provided during metadata creation by user: {}",
                current_user_id,
            )
            abort(400, message="Description field missing")

        try:
            # Create a new metadata session
            metadata_session = Metadata(
                config=config, description=description, user_id=current_user_id
            )
            # insert the metadata session for a user
            metadata_session.add()
            self.logger.info(
                "New metadata session created for user_id {}", current_user_id
            )
        except Exception:
            self.logger.exception("Exception occurred during the Metadata creation")
            abort(500, message="INTERNAL ERROR")
        else:
            response_object = {
                "message": "success",
                "data": {
                    "id": metadata_session.id,
                    "config": metadata_session.config,
                    "description": metadata_session.description,
                },
            }
            return make_response(jsonify(response_object), 201)

    @Auth.token_auth.login_required()
    def get(self):
        """
        Get request for querying all the metadata sessions for a user.
        returns the list of all the metadata sessions associated with a logged in user.
        This requires a Pbench auth token in the header field

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

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
        current_user_id = self.auth.token_auth.current_user().id
        try:
            # Fetch the metadata session
            metadata_sessions = Metadata.query(user_id=current_user_id)
            data = [session.get_json() for session in metadata_sessions]
        except Exception:
            self.logger.exception(
                "Exception occurred while querying the Metadata model"
            )
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "message": "success",
            "data": {"sessions": data},
        }
        return make_response(jsonify(response_object), 200)


class QueryMetadata(Resource):
    """
    Abstracted pbench API for querying a single user metadata session
    """

    def __init__(self, config, logger):
        self.server_config = config
        self.logger = logger

    def verify_metadata(self, session, action):
        current_user_id = Auth.token_auth.current_user().id
        metadata_user_id = session.user_id
        if current_user_id != metadata_user_id:
            self.logger.warning(
                "Metadata {}: Logged in user_id {} is different than the one provided in the URI {}",
                action,
                current_user_id,
                metadata_user_id,
            )
            abort(403, message="Not authorized to perform the specified action")

    @Auth.token_auth.login_required()
    def get(self, id=None):
        """
        Get request for querying a metadata session of a user given a metadata id.
        This requires a Pbench auth token in the header field

        The url requires a metadata session id such as /user/metadata/<string:id>

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "success"
                    "data" {
                        "id": "metadata_id",
                        "config": "Config string"
                        "description": "Description string"
                        }
                }
        """
        if not id:
            self.logger.warning("Metadata id not provided during metadata query")
            abort(400, message="Please provide a metadata id to query")

        try:
            # Fetch the metadata session
            metadata_session = Metadata.query(id=id)
        except Exception:
            self.logger.exception(
                "Exception occurred in the GET request while querying the Metadata model, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        # Verify if the metadata session id in the url belongs to the logged in user
        self.verify_metadata(metadata_session, "get")

        response_object = {
            "message": "success",
            "data": {
                "id": metadata_session.id,
                "config": metadata_session.config,
                "description": metadata_session.description,
            },
        }
        return make_response(jsonify(response_object), 200)

    @Auth.token_auth.login_required()
    def put(self, id=None):
        """
        Put request for updating a metadata session of a user given a metadata id.
        This requires a Pbench auth token in the header field

        The url requires a metadata session id such as /user/metadata/<string:id>

        This requires a JSON data with required user metadata fields to update
        {
            "description": "description",
        }

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "success"
                    "data" {
                        "id": "metadata_id",
                        "config": "Config string"
                        "description": "Description string"
                        }
                }
        """
        if not id:
            self.logger.warning("Metadata id not provided during metadata query")
            abort(400, message="Please provide a metadata id to query")

        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        try:
            metadata_session = Metadata.query(id=id)
        except Exception:
            self.logger.exception(
                "Exception occurred in the PUT request while querying the Metadata model, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        # Verify if the metadata session id in the url belongs to the logged in user
        self.verify_metadata(metadata_session, "put")

        # Check if the metadata payload contain fields that are either protected or
        # not present in the metadata db. If any key in the payload does not match
        # with the column name we will abort the update request.
        non_existent = set(post_data.keys()).difference(
            set(Metadata.__table__.columns.keys())
        )
        if non_existent:
            self.logger.warning(
                "User trying to update fields that are not present in the metadata database. Fields: {}",
                non_existent,
            )
            abort(400, message="Invalid fields in update request payload")
        protected = set(post_data.keys()).intersection(set(Metadata.get_protected()))
        for field in protected:
            if getattr(metadata_session, field) != post_data[field]:
                self.logger.warning(
                    "User trying to update the non-updatable fields. {}: {}",
                    field,
                    post_data[field],
                )
                abort(403, message="Invalid update request payload")
        try:
            metadata_session.update(**post_data)
            self.logger.info(
                "User metadata session updated, id: {}", metadata_session.id
            )
        except Exception:
            self.logger.exception("Exception occurred updating the Metadata model")
            abort(500, message="INTERNAL ERROR")
        else:
            response_object = {
                "message": "success",
                "data": {
                    "id": metadata_session.id,
                    "config": metadata_session.config,
                    "description": metadata_session.description,
                },
            }
            return make_response(jsonify(response_object), 200)

    @Auth.token_auth.login_required()
    def delete(self, id=None):
        """
        Delete request for deleting a metadata session of a user given a metadata id.
        This requires a Pbench auth token in the header field

        The url requires a metadata session id such as /user/metadata/<string:id>

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "success"
                }
        """
        if not id:
            self.logger.warning("Metadata id not provided during metadata query")
            abort(400, message="Please provide a metadata id to query")

        try:
            # Fetch the metadata session
            metadata_session = Metadata.query(id=id)
        except Exception:
            self.logger.exception(
                "Exception occurred in the Delete request while querying the Metadata model, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        # Verify if the metadata session id in the url belongs to the logged in user
        self.verify_metadata(metadata_session, "delete")

        try:
            # Delete the metadata session
            Metadata.delete(id=id)
        except Exception:
            self.logger.exception(
                "Exception occurred in the while deleting the metadata entry, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "message": "success",
        }
        return make_response(jsonify(response_object), 200)
