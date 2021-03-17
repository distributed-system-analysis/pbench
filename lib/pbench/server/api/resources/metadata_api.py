from flask_restful import Resource, abort
from flask import request, make_response, jsonify
from pbench.server.database.models.metadata import UserMetadata
from pbench.server.api.auth import Auth


def verify_metadata(metadata, logger):
    current_user = Auth.token_auth.current_user()
    metadata_user_id = metadata.user_id
    if current_user is None:
        # The request is not from a logged-in user
        if metadata_user_id is None:
            return True
        logger.warning(
            "Metadata user verification: Public user is trying to access private metadata object for user {}",
            metadata_user_id,
        )
        return False
    if current_user.id != metadata_user_id and not current_user.is_admin():
        logger.warning(
            "Metadata user verification: Logged in user_id {} is different than the one provided in the URI {}",
            current_user.id,
            metadata_user_id,
        )
        return False
    return True


class CreateMetadata(Resource):
    """
    Abstracted pbench API for handling user metadata
    """

    def __init__(self, config, logger, auth):
        self.server_config = config
        self.logger = logger
        self.auth = auth

    @Auth.token_auth.login_required()
    def post(self):
        """
        Post request for creating metadata instance for a user.

        The url requires a metadata object key such as /metadata/<key>

        This requires a JSON data with required user metadata fields
        {
            "key": "Metadata_key" # e.g favorite/saved_view
            "value": "blog text" <Client defined text, can be a string of json>,
        }

        Authorization token must be included in the header for creating metadata object
            Authorization:   Bearer <Pbench authentication token (user received upon login)>
        If the authorization header is not present, the user can not create the metadata objects on the server

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

        current_user_id = self.auth.token_auth.current_user().id

        value = post_data.get("value")
        if value is None:
            self.logger.warning(
                "Value not provided during metadata creation. User_id: {}",
                current_user_id,
            )
            abort(400, message="Value field missing")

        metadata_key = post_data.get("key")
        if metadata_key is None:
            self.logger.warning(
                "Key not provided during metadata creation. User_id: {}",
                current_user_id,
            )
            abort(400, message="Key field missing")

        try:
            # Create a new metadata object
            metadata_object = UserMetadata(
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
        If the Pbench authorization token is provided in the header,
        we return the list of all the metadata objects of a specified
        key associated with a logged in user.

        If the authorization token is not provided in the header,
        the access is restricted to only public metadata objects.

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
            metadata_objects = UserMetadata.query(
                user_id=current_user_id, key=key.lower()
            )
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

    @Auth.token_auth.login_required(optional=True)
    def get(self, id):
        """
        Get request for querying a metadata object of a user given a metadata id.
        This requires a Pbench auth token in the header field if the metadata object is private to a user

        If the authorization token is not provided in the header, only public metadata objects are accessible

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
            metadata_objects = UserMetadata.query(id=id)
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
        if not verify_metadata(metadata_object, self.logger):
            abort(403, message="Not authorized to get the metadata object")

        response_object = {
            "data": metadata_object.get_json(
                include=["id", "value", "created", "updated", "key"]
            ),
        }
        return make_response(jsonify(response_object), 200)

    @Auth.token_auth.login_required()
    def put(self, id):
        """
        Put request for updating a metadata object of a user given a metadata id.
        This requires a Pbench auth token in the header field.
        Public metadata objects are read-only accept for an admin users.

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
            abort(400, message="Missing metadata id in the URI for update operation")

        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        try:
            metadata_objects = UserMetadata.query(id=id)
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
        if not verify_metadata(metadata_object, self.logger):
            abort(403, message="Not authorized to update the metadata object")

        # Check if the metadata payload contain fields that are either protected or
        # not present in the metadata db. If any key in the payload does not match
        # with the column name we will abort the update request.
        non_existent = set(post_data.keys()).difference(
            set(UserMetadata.__table__.columns.keys())
        )
        if non_existent:
            self.logger.warning(
                "User trying to update fields that are not present in the metadata database. Fields: {}",
                non_existent,
            )
            abort(400, message="Invalid fields in update request payload")
        protected = set(post_data.keys()).intersection(
            set(UserMetadata.get_protected())
        )
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

    @Auth.token_auth.login_required()
    def delete(self, id):
        """
        Delete request for deleting a metadata object of a user given a metadata id.
        This requires a Pbench auth token in the header field.
        Public metadata objects can only be deleted by admin users.

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
            abort(400, message="Missing metadata id in the URI for delete operation")

        try:
            # Fetch the metadata object
            metadata_objects = UserMetadata.query(id=id)
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
        if not verify_metadata(metadata_object, self.logger):
            abort(403, message="Not authorized to DELETE the metadata object")

        try:
            # Delete the metadata object
            UserMetadata.delete(id=id)
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


class PublishMetadata(Resource):
    """
    Abstracted pbench API for handling user metadata
    """

    def __init__(self, config, logger):
        self.server_config = config
        self.logger = logger

    @Auth.token_auth.login_required()
    def post(self, id):
        """
        Post request for publishing the metadata object for public access.
        This requires a Pbench auth token in the header field. Only authorized users can make their metadata public.
        Right now once the metadata object is made public it can not be reverted back to the private entity
        TODO: Is it desirable to be able to revert the object back as a private entity

        Headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "Metadata object is published"
                }
        """
        if id is None:
            self.logger.warning("Metadata id not provided during metadata query")
            abort(400, message="Missing metadata id in the post request uri")

        try:
            # Fetch the metadata object
            metadata_objects = UserMetadata.query(id=id)
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
        if not verify_metadata(metadata_object, self.logger):
            abort(403, message="Not authorized to publish the metadata object")

        try:
            # Update the metadata object user_id to Null to make them public
            metadata_object.update(**{"user_id": None})
        except Exception:
            self.logger.exception(
                "Exception occurred in the Delete request while querying the Metadata model, id: {}",
                id,
            )
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "message": "Metadata object is published",
        }
        return make_response(jsonify(response_object), 200)
