from flask_restful import Resource, abort
from flask import request, make_response, jsonify
from pbench.server.database.models.metadata import Metadata
from pbench.server.api.auth import Auth


class CreateMetadata(Resource):
    """
    Abstracted pbench API for handling user metadata
    """

    def __init__(self, config, logger, auth):
        self.server_config = config
        self.logger = logger
        self.auth = auth

    @Auth.token_auth.login_required(optional=True)
    def post(self):
        """
        Post request for creating metadata instance for a user.

        The url requires a metadata object key such as /metadata/<key>

        This requires a JSON data with required user metadata fields
        {
            "key": "Metadata_key" # e.g favorite/saved_view
            "value": "blog text" <Client defined text, can be a string of json>,
        }

        Authorization header can be included as
            Authorization:   Bearer <Pbench authentication token (user received upon login)>
        If the authorization header is not present, the created metadata object becomes public by default

        :return: JSON Payload
            response_object = {
                    "data" {
                        "id": "metadata_id",
                        "created": "datetime string",
                        "updated": "datetime string",
                        "key": "user defined key"
                        }
                }
        """
        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        value = post_data.get("value")
        if value is None:
            self.logger.warning("Value not provided during metadata creation.")
            abort(400, message="Value field missing")

        metadata_key = post_data.get("key")
        if metadata_key is None:
            self.logger.warning("Key not provided during metadata creation.")
            abort(400, message="Key field missing")

        current_user = self.auth.token_auth.current_user()
        if current_user:
            current_user_id = current_user.id
        else:
            current_user_id = None

        try:
            # Create a new metadata object
            metadata_object = Metadata(
                value=value, key=metadata_key.lower(), user_id=current_user_id
            )
            # insert the metadata object for a user
            metadata_object.add()
            self.logger.info(
                "New metadata object created for user_id {}", current_user_id
            )
        except Exception:
            self.logger.exception("Exception occurred during the Metadata creation")
            abort(500, message="INTERNAL ERROR")
        else:
            response_object = {
                "data": metadata_object.get_json(
                    include=["id", "created", "updated", "key"]
                ),
            }
            return make_response(jsonify(response_object), 201)


class GetMetadata(Resource):
    """
    Abstracted pbench API for handling user metadata
    """

    def __init__(self, config, logger, auth):
        self.server_config = config
        self.logger = logger
        self.auth = auth

    @Auth.token_auth.login_required(optional=True)
    def get(self, key):
        """
        Get request for querying all the metadata objects for a user.
        returns the list of all the metadata objects of a specified key associated with a logged in user.
        If the user is not logged in we return all the public metadata objects of a specified key.
        This requires a Pbench auth token in the header field

        Optional headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "data": [
                            {"id": "metadata_id",
                            "value": "client text blob",
                            "created": "datetime string",
                            "updated": "datetime string", }, ...]
                }
        """
        if key is None:
            self.logger.warning("Metadata key not provided during metadata query")
            abort(400, message="Missing metadata key in the get request uri")

        current_user = self.auth.token_auth.current_user()
        if current_user:
            current_user_id = current_user.id
        else:
            current_user_id = None
        try:
            # Query the metadata object with a given key
            metadata_objects = Metadata.query(user_id=current_user_id, key=key.lower())
            data = [
                metadata.get_json(include=["id", "created", "updated", "value"])
                for metadata in metadata_objects
            ]
        except Exception:
            self.logger.exception(
                "Exception occurred while querying the Metadata model"
            )
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "data": data,
        }
        return make_response(jsonify(response_object), 200)


class QueryMetadata(Resource):
    """
    Abstracted pbench API for querying a single user metadata object
    """

    def __init__(self, config, logger):
        self.server_config = config
        self.logger = logger

    def verify_metadata(self, metadata):
        current_user = Auth.token_auth.current_user()
        metadata_user_id = metadata.user_id
        if current_user is None:
            # The request is not from a logged-in user
            if metadata_user_id is None:
                return True
            self.logger.warning(
                "Metadata user verification: Public user is trying to access private metadata object for user {}",
                metadata_user_id,
            )
            return False
        if current_user.id != metadata_user_id and not current_user.is_admin():
            self.logger.warning(
                "Metadata user verification: Logged in user_id {} is different than the one provided in the URI {}",
                current_user.id,
                metadata_user_id,
            )
            return False
        return True

    @Auth.token_auth.login_required(optional=True)
    def get(self, id=None):
        """
        Get request for querying a metadata object of a user given a metadata id.
        This requires a Pbench auth token in the header field if the metadata object is private to a user


        The url requires a metadata object id such as /user/metadata/<int:id>

        Optional headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "data": {
                        "id": "metadata_id",
                        "value": "client text blob"
                        "created": "Datetime string"
                        "updated": "Datetime String"
                        "key": "key string"
                        }
                }
        """
        if id is None:
            self.logger.warning("Metadata id not provided during metadata query")
            abort(400, message="Missing metadata id in the URI")

        try:
            # Fetch the metadata object
            metadata_objects = Metadata.query(id=id)
        except Exception:
            self.logger.exception(
                "Exception occurred in the GET request while querying the Metadata model, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        if metadata_objects:
            metadata_object = metadata_objects[0]
        else:
            abort(404, message="Not found")

        # Verify if the metadata object id in the url belongs to the logged in user
        if not self.verify_metadata(metadata_object):
            abort(403, message="Not authorized to perform the GET request")

        response_object = {
            "data": metadata_object.get_json(
                include=["id", "value", "created", "updated", "key"]
            ),
        }
        return make_response(jsonify(response_object), 200)

    @Auth.token_auth.login_required(optional=True)
    def put(self, id=None):
        """
        Put request for updating a metadata object of a user given a metadata id.
        This requires a Pbench auth token in the header field

        The url requires a metadata object id such as /user/metadata/<int:id>

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
                    "data": {
                        "id": "metadata_id",
                        "created": "Datetime string"
                        "updated": "Datetime String"
                        "key": "key string"
                        }
                }
        """
        if id is None:
            self.logger.warning("Metadata id not provided during metadata query")
            abort(400, message="Please provide a metadata id to query")

        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        try:
            metadata_objects = Metadata.query(id=id)
        except Exception:
            self.logger.exception(
                "Exception occurred in the PUT request while querying the Metadata model, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        if metadata_objects:
            metadata_object = metadata_objects[0]
        else:
            abort(404, message="Not found")

        # Verify if the metadata object id in the url belongs to the logged in user
        if not self.verify_metadata(metadata_object):
            abort(403, message="Not authorized to perform the PUT request")

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
            if getattr(metadata_object, field) != post_data[field]:
                self.logger.warning(
                    "User trying to update the non-updatable fields. {}: {}",
                    field,
                    post_data[field],
                )
                abort(403, message="Invalid update request payload")
        try:
            metadata_object.update(**post_data)
            self.logger.info("User metadata object updated, id: {}", metadata_object.id)
        except Exception:
            self.logger.exception("Exception occurred updating the Metadata model")
            abort(500, message="INTERNAL ERROR")
        else:
            response_object = {
                "data": metadata_object.get_json(["id", "created", "updated", "key"]),
            }
            return make_response(jsonify(response_object), 200)

    @Auth.token_auth.login_required(optional=True)
    def delete(self, id=None):
        """
        Delete request for deleting a metadata object of a user given a metadata id.
        This requires a Pbench auth token in the header field

        The url requires a metadata object id such as /user/metadata/<int:id>

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "success"
                }
        """
        if id is None:
            self.logger.warning("Metadata id not provided during metadata query")
            abort(400, message="Please provide a metadata id to query")

        try:
            # Fetch the metadata object
            metadata_objects = Metadata.query(id=id)
        except Exception:
            self.logger.exception(
                "Exception occurred in the Delete request while querying the Metadata model, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        if metadata_objects:
            metadata_object = metadata_objects[0]
        else:
            abort(404, message="Not found")

        # Verify if the metadata object id in the url belongs to the logged in user
        if not self.verify_metadata(metadata_object):
            abort(403, message="Not authorized to perform the DELETE request")

        try:
            # Delete the metadata object
            Metadata.delete(id=id)
        except Exception:
            self.logger.exception(
                "Exception occurred in the while deleting the metadata entry, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "message": "Metadata object deleted",
        }
        return make_response(jsonify(response_object), 200)
