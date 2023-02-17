from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import NamedTuple

from email_validator import EmailNotValidError
from flask import current_app, jsonify, make_response, request
from flask_bcrypt import check_password_hash
from flask_restful import abort, Resource
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import pbench.server.auth.auth as Auth
from pbench.server.database.database import Database
from pbench.server.database.models.auth_tokens import AuthToken
from pbench.server.database.models.server_settings import ServerSetting
from pbench.server.database.models.users import User


class RegisterUser(Resource):
    """
    Abstracted pbench API for registering a new user
    """

    def __init__(self, config):
        self.server_config = config

    def post(self):
        """
        Post request for registering a new user.
        This requires a JSON data with required user fields
        {
            "username": "username",
            "password": "password",
            "first_name": first_name,
            "last_name": "last_name",
            "email": "user@domain.com"
        }

        Required headers include

            Content-Type:   application/json
            Accept:         application/json

        :return:
            Success: 201 with empty payload
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        To get the auth token user has to perform the login action
        """
        disabled = ServerSetting.get_disabled()
        if disabled:
            abort(HTTPStatus.SERVICE_UNAVAILABLE, **disabled)

        # get the post data
        user_data = request.get_json()
        if not user_data:
            current_app.logger.warning("Invalid json object: {}", request.url)
            abort(HTTPStatus.BAD_REQUEST, message="Invalid json object in request")

        username = user_data.get("username")
        if not username:
            current_app.logger.warning("Missing username field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing username field")
        username = username.lower()
        if User.is_admin_username(username):
            current_app.logger.warning("User tried to register with admin username")
            abort(
                HTTPStatus.BAD_REQUEST,
                message="Please choose another username",
            )

        # check if provided username already exists
        try:
            user = User.query(username=user_data.get("username"))
        except Exception:
            current_app.logger.exception("Exception while querying username")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        if user:
            current_app.logger.warning(
                "A user tried to re-register. Username: {}", user.username
            )
            abort(HTTPStatus.FORBIDDEN, message="Provided username is already in use.")

        password = user_data.get("password")
        if not password:
            current_app.logger.warning("Missing password field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing password field")

        email_id = user_data.get("email")
        if not email_id:
            current_app.logger.warning("Missing email field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing email field")
        # check if provided email already exists
        try:
            user = User.query(email=email_id)
        except Exception:
            current_app.logger.exception("Exception while querying user email")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        if user:
            current_app.logger.warning(
                "A user tried to re-register. Email: {}", user.email
            )
            abort(HTTPStatus.FORBIDDEN, message="Provided email is already in use")

        first_name = user_data.get("first_name")
        if not first_name:
            current_app.logger.warning("Missing first_name field")
            abort(HTTPStatus.BAD_REQUEST, message="Missing first_name field")

        last_name = user_data.get("last_name")
        if not last_name:
            current_app.logger.warning("Missing last_name field")
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
            current_app.logger.info(
                "New user registered, username: {}, email: {}", username, email_id
            )
            return "", HTTPStatus.CREATED
        except EmailNotValidError:
            current_app.logger.warning("Invalid email {}", email_id)
            abort(HTTPStatus.BAD_REQUEST, message=f"Invalid email: {email_id}")
        except Exception:
            current_app.logger.exception("Exception while registering a user")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")


class Login(Resource):
    """
    Pbench API for User Login or generating an auth token
    """

    def __init__(self, config):
        self.server_config = config
        self.token_expire_duration = self.server_config.get(
            "pbench-server", "token_expiration_duration"
        )

    def post(self):
        """
        Post request for logging in user.
        The user is allowed to re-login multiple times and each time a new
        valid auth token will be returned.

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
            current_app.logger.warning("Invalid json object: {}", request.url)
            abort(HTTPStatus.BAD_REQUEST, message="Invalid json object in request")

        username = post_data.get("username")
        if not username:
            current_app.logger.warning("Username not provided during the login process")
            abort(HTTPStatus.BAD_REQUEST, message="Please provide a valid username")

        password = post_data.get("password")
        if not password:
            current_app.logger.warning("Password not provided during the login process")
            abort(HTTPStatus.BAD_REQUEST, message="Please provide a valid password")

        try:
            # fetch the user data
            user = User.query(username=username)
        except Exception:
            current_app.logger.exception("Exception occurred during user login")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        if not user:
            current_app.logger.warning(
                "No user found in the db for Username: {} while login", username
            )
            abort(HTTPStatus.UNAUTHORIZED, message="Bad login")

        # Validate the password
        if not check_password_hash(user.password, password):
            current_app.logger.warning(
                "Wrong password for user: {} during login", username
            )
            abort(HTTPStatus.UNAUTHORIZED, message="Bad login")

        auth_token, expiration = Auth.encode_auth_token(
            time_delta=timedelta(minutes=int(self.token_expire_duration)),
            user_id=user.id,
        )

        # Add the new auth token to the database for later access
        try:
            token = AuthToken(token=auth_token, expiration=expiration)
            user.add_token(token)
        except IntegrityError:
            current_app.logger.warning(
                "Duplicate auth token got created, user might have tried to re-login immediately"
            )
            abort(HTTPStatus.CONFLICT, message="Login collision; please wait and retry")
        except SQLAlchemyError as e:
            current_app.logger.error(
                "SQLAlchemy Exception while logging in a user {}", type(e)
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        except Exception:
            current_app.logger.exception("Exception while logging in a user")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        else:
            current_app.logger.debug(
                "New auth token registered for user {}", user.username
            )

        # We take the opportunity to remove any expired tokens for ANY user
        # since we don't have a background reaper task dedicated to this kind
        # of an operation.
        try:
            Database.db_session.query(AuthToken).filter(
                AuthToken.expiration <= datetime.now(timezone.utc)
            ).delete()
            Database.db_session.commit()
        except Exception as exc:
            Database.db_session.rollback()
            current_app.logger.error(
                "Error encountered removing expired tokens during login for user {}: {}",
                user.username,
                exc,
            )

        response_object = {
            "auth_token": auth_token,
            "username": username,
        }
        return make_response(jsonify(response_object), HTTPStatus.OK)


class Logout(Resource):
    """
    Pbench API for User logout and deleting an auth token
    """

    def __init__(self, config):
        self.server_config = config

    def post(self):
        """
        post request for logging out a user for the current auth token.
        This requires a Pbench authentication auth token in the header field

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received
                             upon login)>

        :return:
            Success: 200 with empty payload
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        """
        auth_token = Auth.get_auth_token()
        state = Auth.verify_internal_token(auth_token)

        # If the token is invalid, it won't be in the database; valid but
        # expired tokens may have been removed from the database by other
        # requests; otherwise, the token should be in the database.  If the
        # token is valid and found in the database, it must be associated with
        # a user (assertion handled by database schema), so we can simply remove
        # it from the database.

        if state == Auth.TokenState.INVALID:
            current_app.logger.debug("User logout with invalid token: {}", auth_token)
        else:
            current_app.logger.debug("User logout with {} token: {}", state, auth_token)
            try:
                AuthToken.delete(auth_token)
            except Exception:
                current_app.logger.exception(
                    "Exception occurred deleting auth token {!r}",
                    auth_token,
                )
                abort(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message="INTERNAL ERROR",
                )

        return "", HTTPStatus.OK


class UserAPI(Resource):
    """
    Abstracted pbench API to get user data
    """

    TargetUser = NamedTuple(
        "TargetUser",
        [("target_user", User), ("http_status", HTTPStatus), ("http_message", str)],
    )

    def get_valid_target_user(
        self, target_username: str, request_type: str
    ) -> "UserAPI.TargetUser":
        """
        Helper function to determine whether the API call is permitted for the target username
        Right now it is only permitted for an admin user and the target user itself.
        This returns a target User on success or None on failure; in the case of failure,
        also returns the corresponding HTTP status code and message string
        """
        current_user = Auth.token_auth.current_user()
        if current_user.username == target_username:
            return UserAPI.TargetUser(
                target_user=current_user, http_status=HTTPStatus.OK, http_message=""
            )
        if current_user.is_admin():
            target_user = User.query(username=target_username)
            if target_user:
                return UserAPI.TargetUser(
                    target_user=target_user, http_status=HTTPStatus.OK, http_message=""
                )

            current_app.logger.warning(
                "User {} requested {} operation but user {} is not found.",
                current_user.username,
                request_type,
                target_username,
            )
            return UserAPI.TargetUser(
                target_user=None,
                http_status=HTTPStatus.NOT_FOUND,
                http_message=f"User {target_username} not found",
            )

        current_app.logger.warning(
            "User {} is not authorized to {} user {}.",
            current_user.username,
            request_type,
            target_username,
        )
        return UserAPI.TargetUser(
            target_user=None,
            http_status=HTTPStatus.FORBIDDEN,
            http_message=f"Not authorized to access user {target_username}",
        )

    @Auth.token_auth.login_required()
    def get(self, target_username):
        """
        Get request for getting user data.
        This requires a Pbench auth token in the header field

        Required headers include

            Content-Type:   application/json
            Accept:         application/json
            Authorization:  Bearer Pbench_auth_token (user received upon login)

        :return: JSON Payload
            Success: 200,
                    response_object = {
                        "username": <username>,
                        "first_name": <firstName>,
                        "last_name": <lastName>,
                        "registered_on": <registered_on>,
                    }
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        """
        disabled = ServerSetting.get_disabled(readonly=True)
        if disabled:
            abort(HTTPStatus.SERVICE_UNAVAILABLE, **disabled)

        result = self.get_valid_target_user(target_username, "GET")
        if not result.target_user:
            abort(result.http_status, message=result.http_message)
        response_object = result.target_user.get_json()
        return make_response(jsonify(response_object), HTTPStatus.OK)

    @Auth.token_auth.login_required()
    def put(self, target_username):
        """
        PUT request for updating user data.
        This requires a Pbench auth token in the header field

        This requires a JSON data with required user registration fields that needs an update
        Example Json:
        {
            "first_name": "new_name",
            "password": "password",
            ...
        }

        Required headers include

            Content-Type:   application/json
            Accept:         application/json
            Authorization:  Bearer Pbench_auth_token (user received upon login)

        :return: JSON Payload
            Success: 200,
                    response_object = {
                        "username": <username>,
                        "first_name": <firstName>,
                        "last_name": <lastName>,
                        "registered_on": <registered_on>,
                    }
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        """
        disabled = ServerSetting.get_disabled()
        if disabled:
            abort(HTTPStatus.SERVICE_UNAVAILABLE, **disabled)

        user_payload = request.get_json()
        if not user_payload:
            current_app.logger.warning("Invalid json object: {}", request.url)
            abort(HTTPStatus.BAD_REQUEST, message="Invalid json object in request")

        result = self.get_valid_target_user(target_username, "PUT")
        if not result.target_user:
            abort(result.http_status, message=result.http_message)

        # Check if the user payload contain fields that are either protected or
        # are not present in the user db. If any key in the payload does not match
        # with the column name we will abort the update request.
        non_existent = set(user_payload.keys()).difference(
            set(User.__table__.columns.keys())
        )
        if non_existent:
            current_app.logger.warning(
                "User trying to update fields that are not present in the user database. Fields: {}",
                non_existent,
            )
            abort(
                HTTPStatus.BAD_REQUEST,
                message="Invalid fields in update request payload",
            )
        # Only admin user will be allowed to change other user's role. However,
        # Admin users will not be able to change their admin role,
        # This is done to prevent last admin user from de-admining him/herself
        protected_db_fields = User.get_protected()
        if (
            not Auth.token_auth.current_user().is_admin()
            or Auth.token_auth.current_user() == result.target_user
        ):
            protected_db_fields.append("role")

        protected = set(user_payload.keys()).intersection(set(protected_db_fields))
        for field in protected:
            if getattr(result.target_user, field) != user_payload[field]:
                current_app.logger.warning(
                    "User trying to update the non-updatable fields. {}: {}",
                    field,
                    user_payload[field],
                )
                abort(HTTPStatus.FORBIDDEN, message="Invalid update request payload")
        try:
            result.target_user.update(**user_payload)
        except Exception:
            current_app.logger.exception(
                "Exception occurred during updating user object"
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        response_object = result.target_user.get_json()
        return make_response(jsonify(response_object), HTTPStatus.OK)

    @Auth.token_auth.login_required()
    def delete(self, target_username):
        """
        Delete request for deleting a user from database.
        This requires a Pbench auth token in the header field

        Required headers include

            Content-Type:   application/json
            Accept:         application/json
            Authorization:   Bearer Pbench_auth_token (user received upon login)

        :return:
            Success: 200 with empty payload
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        """
        disabled = ServerSetting.get_disabled()
        if disabled:
            abort(HTTPStatus.SERVICE_UNAVAILABLE, **disabled)

        result = self.get_valid_target_user(target_username, "DELETE")
        if not result.target_user:
            abort(result.http_status, message=result.http_message)
        # Do not allow admin user to get self deleted via API
        if (
            result.target_user.is_admin()
            and Auth.token_auth.current_user() == result.target_user
        ):
            current_app.logger.warning(
                "Admin user is not allowed to self delete via API call. Username: {}",
                target_username,
            )
            abort(HTTPStatus.FORBIDDEN, message="Not authorized to delete user")

        # If target user is a valid and not an admin proceed to delete
        try:
            User.delete(target_username)
            current_app.logger.info(
                "User entry deleted for user with username: {}, by user: {}",
                target_username,
                Auth.token_auth.current_user().username,
            )
        except Exception:
            current_app.logger.exception(
                "Exception occurred while deleting a user {}",
                target_username,
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        return "", HTTPStatus.OK
