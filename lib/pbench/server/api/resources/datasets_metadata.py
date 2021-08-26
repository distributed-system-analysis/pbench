from http import HTTPStatus
import jwt
from flask import request, jsonify, make_response
from flask_restful import Resource, abort
from flask_bcrypt import check_password_hash
from email_validator import EmailNotValidError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pbench.server.database.models.users import User
from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.api.auth import Auth
from pbench.server.api.resources.query_apis import (
    ElasticBase,
    Parameter,
    ParamType,
    Schema,
)


class DatasetsMetadata(Resource):
    """
    API to set Dataset metadata.
    """

    def __init__(self, config, logger):
        self.server_config = config
        self.logger = logger
        self.schema = Schema(
            Parameter("controller", ParamType.STRING, required=True),
            Parameter("name", ParamType.STRING, required=True),
            Parameter(
                "metadata",
                ParamType.LIST,
                element_type=ParamType.KEYWORD,
                keywords=ElasticBase.METADATA,
            ),
        )

    @Auth.token_auth.login_required()
    def put(self):
        """
        Set or modify the values of client-accessible dataset metadata keys.

        PUT /api/v1/datasets/metadata
        {
            "controller": "ctrlname",
            "name": "datasetname",
            "metadata": [
                "SEEN": True,
                "USER": {
                    "cloud": "AWS",
                    "contact": "john.carter@mars.org"
                }
            ]
        }

        Some metadata accessible via GET /api/v1/datasets/metadata (or from
        /api/v1/datasets/list and /api/v1/datasets/detail) is not modifiable by
        the client, and cannot be specified here, including DELETED, OWNER, and
        ACCESS.
        """
        # get the post data
        user_data = request.get_json()
        if not user_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(HTTPStatus.BAD_REQUEST, message="Invalid json object in request")

        username = user_data.get("username")
        if not username:
            self.logger.warning("Missing username field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing username field")
        username = username.lower()
        if User.is_admin_username(username):
            self.logger.warning("User tried to register with admin username")
            abort(
                HTTPStatus.BAD_REQUEST, message="Please choose another username",
            )

        # check if provided username already exists
        try:
            user = User.query(username=user_data.get("username"))
        except Exception:
            self.logger.exception("Exception while querying username")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        if user:
            self.logger.warning(
                "A user tried to re-register. Username: {}", user.username
            )
            abort(HTTPStatus.FORBIDDEN, message="Provided username is already in use.")

        password = user_data.get("password")
        if not password:
            self.logger.warning("Missing password field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing password field")

        email_id = user_data.get("email")
        if not email_id:
            self.logger.warning("Missing email field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing email field")
        # check if provided email already exists
        try:
            user = User.query(email=email_id)
        except Exception:
            self.logger.exception("Exception while querying user email")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        if user:
            self.logger.warning("A user tried to re-register. Email: {}", user.email)
            abort(HTTPStatus.FORBIDDEN, message="Provided email is already in use")

        first_name = user_data.get("first_name")
        if not first_name:
            self.logger.warning("Missing first_name field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing first_name field")

        last_name = user_data.get("last_name")
        if not last_name:
            self.logger.warning("Missing last_name field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing last_name field")

        try:
            user = User(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email_id,
            )

            # insert the user
            user.add()
            self.logger.info(
                "New user registered, username: {}, email: {}", username, email_id
            )
            return "", HTTPStatus.CREATED
        except EmailNotValidError:
            self.logger.warning("Invalid email {}", email_id)
            abort(HTTPStatus.BAD_REQUEST, message=f"Invalid email: {email_id}")
        except Exception:
            self.logger.exception("Exception while registering a user")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")


class Login(Resource):
    """
    Pbench API for User Login or generating an auth token
    """

    def __init__(self, config, logger, auth):
        self.server_config = config
        self.logger = logger
        self.auth = auth
        self.token_expire_duration = self.server_config.get(
            "pbench-server", "token_expiration_duration"
        )

    def post(self):
        """
        Post request for logging in user.
        The user is allowed to re-login multiple times and each time a new valid auth token will be provided

        This requires a JSON data with required user metadata fields
        {
            "username": "username",
            "password": "password",
        }

        Required headers include

            Content-Type:   application/json
            Accept:         application/json

        :return: JSON Payload
            Success: 200,
                    response_object = {
                        "auth_token": "<authorization_token>"
                        "username": <username>
                    }
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        """
        # get the post data
        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(HTTPStatus.BAD_REQUEST, message="Invalid json object in request")

        username = post_data.get("username")
        if not username:
            self.logger.warning("Username not provided during the login process")
            abort(HTTPStatus.BAD_REQUEST, message="Please provide a valid username")

        password = post_data.get("password")
        if not password:
            self.logger.warning("Password not provided during the login process")
            abort(HTTPStatus.BAD_REQUEST, message="Please provide a valid password")

        try:
            # fetch the user data
            user = User.query(username=username)
        except Exception:
            self.logger.exception("Exception occurred during user login")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        if not user:
            self.logger.warning(
                "No user found in the db for Username: {} while login", username
            )
            abort(HTTPStatus.UNAUTHORIZED, message="Bad login")

        # Validate the password
        if not check_password_hash(user.password, password):
            self.logger.warning("Wrong password for user: {} during login", username)
            abort(HTTPStatus.UNAUTHORIZED, message="Bad login")

        try:
            auth_token = self.auth.encode_auth_token(
                self.token_expire_duration, user.id
            )
        except (
            jwt.InvalidIssuer,
            jwt.InvalidIssuedAtError,
            jwt.InvalidAlgorithmError,
            jwt.PyJWTError,
        ):
            self.logger.exception(
                "Could not encode the JWT auth token for user: {} while login", username
            )
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR",
            )

        # Add the new auth token to the database for later access
        try:
            token = ActiveTokens(token=auth_token)
            # TODO: Decide on the auth token limit per user
            user.update(auth_tokens=token)

            self.logger.info("New auth token registered for user {}", user.email)
        except IntegrityError:
            self.logger.warning(
                "Duplicate auth token got created, user might have tried to re-login immediately"
            )
            abort(HTTPStatus.CONFLICT, message="Login collision; please wait and retry")
        except SQLAlchemyError as e:
            self.logger.error(
                "SQLAlchemy Exception while logging in a user {}", type(e)
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        except Exception:
            self.logger.exception("Exception while logging in a user")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        response_object = {
            "auth_token": auth_token,
            "username": username,
        }
        return make_response(jsonify(response_object), HTTPStatus.OK)
