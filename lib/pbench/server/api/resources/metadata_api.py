from flask_restful import Resource, abort
from flask import request, make_response, jsonify
from pbench.server.database.models.metadata import Metadata, MetadataKeys
from pbench.server.api.auth import Auth


class UserMetadata(Resource):
    """
    Abstracted pbench API for handling user metadata by using graphql schema
    """

    def __init__(self, config, logger, auth):
        self.server_config = config
        self.logger = logger
        self.auth = auth

    @Auth.token_auth.login_required(optional=True)
    def post(self, key):
        """
        Post request for creating metadata instance for a user.

        The url requires a metadata session key such as /metadata/<key>
        the only keys acceptable to create the metadata sessions are favourite/saved

        This requires a JSON data with required user metadata fields
        {
            "value": "blog text" <Client defined text, can be a string of json>,
        }
        Example: {"value": '{"config": "config", "description": "description"}'}

        Authorization header can be included as
            Authorization:   Bearer <Pbench authentication token (user received upon login)>
        If the authorization header is not present, the created metadata session becomes public by default

        :return: JSON Payload
            response_object = {
                    "message": "success"
                    "data" {
                        "id": "metadata_id",
                        "value": "client text blob",
                        "created": "datetime string",
                        "updated": "datetime string",
                        "key": favorite/saved
                        }
                }
        """
        metadata_key = key.upper()
        if metadata_key not in [key.name for key in MetadataKeys]:
            self.logger.warning(
                "Invalid Metadata key provided during metadata creation. Key: {}",
                metadata_key,
            )
            abort(
                400,
                message="Invalid metadata key. Key need to be either Favorite/Saved",
            )

        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        current_user = self.auth.token_auth.current_user()
        if current_user:
            current_user_id = current_user.id
        else:
            current_user_id = None

        value = post_data.get("value")
        if not value:
            self.logger.warning(
                "value not provided during metadata creation. user_id: {}",
                current_user_id,
            )
            abort(400, message="Value field missing")

        try:
            # Create a new metadata session
            metadata_session = Metadata(
                value=value, key=metadata_key, user_id=current_user_id
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
                "data": metadata_session.get_json(),
            }
            return make_response(jsonify(response_object), 201)

    @Auth.token_auth.login_required(optional=True)
    def get(self, key):
        """
        Get request for querying all the metadata sessions for a user.
        returns the list of all the metadata sessions associated with a logged in user.
        This requires a Pbench auth token in the header field

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "success"
                    "data": {
                        "sessions": [
                            {"id": "metadata_id",
                            "value": "client text blob",
                            "key": "key string",
                            "created": "datetime string",
                            "updated": "datetime string", },
                            {}]
                        }
                }
        """
        if not key:
            self.logger.warning("Metadata key not provided during metadata query")
            abort(400, message="Missing metadata key in the query url")

        current_user = self.auth.token_auth.current_user()
        if current_user:
            current_user_id = current_user.id
        else:
            current_user_id = None
        print(current_user_id)
        try:
            # Fetch the metadata sessions
            # If the key is favorite, we return only favorite sessions,
            # else we return all the saved and favorite sessions
            if key.upper() == "FAVORITE":
                metadata_sessions = Metadata.query(
                    user_id=current_user_id, key=MetadataKeys[key.upper()].value
                )
            else:
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

        The url requires a metadata session id such as /user/metadata/<int:id>

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "success",
                    "data": {
                        "id": "metadata_id",
                        "value": "client text blob"
                        "created": "Datetime string"
                        "updated": "Datetime String"
                        "key": "key string"
                        }
                }
        """
        if not id:
            self.logger.warning("Metadata id not provided during metadata query")
            abort(400, message="Please provide a metadata id to query")

        try:
            # Fetch the metadata session
            metadata_session = Metadata.query(id=id)[0]
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
            "data": metadata_session.get_json(),
        }
        return make_response(jsonify(response_object), 200)

    @Auth.token_auth.login_required()
    def put(self, id=None):
        """
        Put request for updating a metadata session of a user given a metadata id.
        This requires a Pbench auth token in the header field

        The url requires a metadata session id such as /user/metadata/<int:id>

        This requires a JSON data with required user metadata fields to update
        {
            "value": "new text value",
            ...
        }
        To update the value field, it is required to send the complete text blob again

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "success",
                    "data": {
                        "id": "metadata_id",
                        "value": "client text blob"
                        "created": "Datetime string"
                        "updated": "Datetime String"
                        "key": "key string"
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
            metadata_session = Metadata.query(id=id)[0]
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
                "data": metadata_session.get_json(),
            }
            return make_response(jsonify(response_object), 200)

    @Auth.token_auth.login_required()
    def delete(self, id=None):
        """
        Delete request for deleting a metadata session of a user given a metadata id.
        This requires a Pbench auth token in the header field

        The url requires a metadata session id such as /user/metadata/<int:id>

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
            metadata_session = Metadata.query(id=id)[0]
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
