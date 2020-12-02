import jwt
from flask import request, jsonify, make_response
from flask_restful import Resource, abort
from flask_bcrypt import check_password_hash
from email_validator import EmailNotValidError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pbench.server.database.models.users import User
from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.api.auth import Auth


class RegisterUser(Resource):
    """
    Abstracted pbench API for registering a new user
    """

    def __init__(self, config, logger):
        self.server_config = config
        self.logger = logger

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

        :return: JSON Payload
        if we succeed to add a user entry in the database, the returned response_object will look like the following:
            response_object = {
                    "message": "Successfully registered."/"failure message",
                }
        To get the auth token user has to perform the login action
        """
        # get the post data
        user_data = request.get_json()
        if not user_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        username = user_data.get("username")
        if not username:
            self.logger.warning("Missing username field")
            abort(400, message="Missing username field")
        username = username.lower()
        if User.is_admin_username(username):
            self.logger.warning("User tried to register with admin username")
            abort(
                400, message="Please choose another username",
            )

        # check if provided username already exists
        try:
            user = User.query(username=user_data.get("username"))
        except Exception:
            self.logger.exception("Exception while querying username")
            abort(500, message="INTERNAL ERROR")
        if user:
            self.logger.warning(
                "A user tried to re-register. Username: {}", user.username
            )
            abort(403, message="Provided username is already in use.")

        password = user_data.get("password")
        if not password:
            self.logger.warning("Missing password field")
            abort(400, message="Missing password field")

        email_id = user_data.get("email")
        if not email_id:
            self.logger.warning("Missing email field")
            abort(400, message="Missing email field")
        # check if provided email already exists
        try:
            user = User.query(email=email_id)
        except Exception:
            self.logger.exception("Exception while querying user email")
            abort(500, message="INTERNAL ERROR")
        if user:
            self.logger.warning("A user tried to re-register. Email: {}", user.email)
            abort(403, message="Provided email is already in use")

        first_name = user_data.get("first_name")
        if not first_name:
            self.logger.warning("Missing firstName field")
            abort(400, message="Missing firstName field")

        last_name = user_data.get("last_name")
        if not last_name:
            self.logger.warning("Missing lastName field")
            abort(400, message="Missing lastName field")

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

            response_object = {
                "message": "Successfully registered.",
            }
            response = jsonify(response_object)
            response.status_code = 201
            return make_response(response, 201)
        except EmailNotValidError:
            self.logger.warning("Invalid email {}", email_id)
            abort(400, message=f"Invalid email: {email_id}")
        except Exception:
            self.logger.exception("Exception while registering a user")
            abort(500, message="INTERNAL ERROR")


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

    @Auth.token_auth.login_required(optional=True)
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
        if we succeed to decrypt the password hash, the returned response_object will include the auth_token
            response_object = {
                    "message": "Successfully logged in."/"failure message",
                    "auth_token": "<authorization_token>", # Will not present if failed
                }
        """
        # get the post data
        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        username = post_data.get("username")
        if not username:
            self.logger.warning("Username not provided during the login process")
            abort(400, message="Please provide a valid username")

        password = post_data.get("password")
        if not password:
            self.logger.warning("Password not provided during the login process")
            abort(400, message="Please provide a valid password")

        try:
            # fetch the user data
            user = User.query(username=username)
        except Exception:
            self.logger.exception("Exception occurred during user login")
            abort(500, message="INTERNAL ERROR")

        if not user:
            self.logger.warning(
                "No user found in the db for Username: {} while login", username
            )
            abort(403, message="Bad login")

        # Validate the password
        if not check_password_hash(user.password, password):
            self.logger.warning("Wrong password for user: {} during login", username)
            abort(401, message="Bad login")

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
                500, message="INTERNAL ERROR",
            )

        # check if the user is already logged in, in case the request has a an authorization header included
        # We would still proceed to login and return a new auth token to the user
        if user == self.auth.token_auth.current_user():
            self.logger.warning("User already logged in and trying to re-login")
            if self.auth.token_auth.get_auth()["token"] == auth_token:
                # If a user attempts to re-login immediately within a millisecond,
                # the new auth token will be same as the one present in the header
                # Therefore we will not fulfill the re-login request
                self.logger.info("Attempted immediate re-login")
                abort(403, message="Retry login after some time")

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
            abort(409, message="Retry login after some time")
        except SQLAlchemyError as e:
            self.logger.error(
                "SQLAlchemy Exception while logging in a user {}", type(e)
            )
            abort(500, message="INTERNAL ERROR")
        except Exception:
            self.logger.exception("Exception while logging in a user")
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "message": "Successfully logged in.",
            "auth_token": auth_token,
            "username": username,
        }
        return make_response(jsonify(response_object), 200)


class Logout(Resource):
    """
    Pbench API for User logout and deleting an auth token
    """

    def __init__(self, config, logger, auth):
        self.server_config = config
        self.logger = logger
        self.auth = auth

    @Auth.token_auth.login_required()
    def post(self):
        """
        post request for logging out a user for the current auth token.
        This requires a Pbench authentication auth token in the header field

        Required headers include
            Authorization:   Bearer <Pbench authentication token (user received upon login)>

        :return: JSON Payload
            response_object = {
                    "message": "Successfully logged out."/"failure message",
                }
        """
        auth_token = self.auth.token_auth.get_auth()["token"]
        user = self.auth.token_auth.current_user()

        try:
            ActiveTokens.delete(auth_token)
            self.logger.info(
                "Auth token entry deleted for user with username {}", user.email
            )
        except Exception:
            self.logger.exception("Exception occurred during deleting the user entry")
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "message": "Successfully logged out.",
        }
        return make_response(jsonify(response_object), 200)


class UserAPI(Resource):
    """
    Abstracted pbench API to get user data
    """

    def __init__(self, logger, auth):
        self.logger = logger
        self.auth = auth

    @Auth.token_auth.login_required()
    def get(self, username):
        """
        Get request for getting user data.
        This requires a Pbench auth token in the header field

        Required headers include

            Content-Type:   application/json
            Accept:         application/json
            Authorization:  Bearer Pbench_auth_token (user received upon login)

        :return: JSON Payload
            response_object = {
                    "message": "Success"/"failure message",
                    "data": {
                        "username": <username>,
                        "firstName": <firstName>,
                        "lastName": <lastName>,
                        "registered_on": registered_on,
                    }
                }
        """
        try:
            user, verified = self.auth.verify_user(username)
        except Exception:
            self.logger.exception("Exception occurred during verifying the user")
            abort(500, message="INTERNAL ERROR")

        # TODO: Check if the user has the right privileges
        if verified:
            response_object = {
                "status": "success",
                "data": user.get_json(),
            }
            return make_response(jsonify(response_object), 200)
        elif user.is_admin():
            try:
                target_user = User.query(username=username)
                response_object = {
                    "message": "success",
                    "data": target_user.get_json(),
                }
                return make_response(jsonify(response_object), 200)
            except Exception:
                self.logger.exception(
                    "Exception occurred while querying the user. Username: {}", username
                )
                abort(500, message="INTERNAL ERROR")
        else:
            self.logger.warning(
                "User {} is not authorized to delete user {}.", user.username, username,
            )
            abort(
                403,
                message=f"Not authorized to access information about user {username}",
            )

    @Auth.token_auth.login_required()
    def put(self, username):
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
            response_object = {
                    "message": "Success"/"failure message",
                    "data": {
                        "username": <username>,
                        "first_name": <firstName>,
                        "last_name": <lastName>,
                        "registered_on": registered_on,
                    }
                }
        """
        post_data = request.get_json()
        if not post_data:
            self.logger.warning("Invalid json object: {}", request.url)
            abort(400, message="Invalid json object in request")

        try:
            user, verified = self.auth.verify_user(username)
        except Exception:
            self.logger.exception("Exception occurred while verifying the user")
            abort(500, message="INTERNAL ERROR")

        # TODO: Check if the user has the right privileges
        if not verified:
            self.logger.warning(
                "User {} is not authorized to delete user {}.", user.username, username,
            )
            abort(
                403,
                message=f"Not authorized to update information about user {username}",
            )

        # Check if the user payload contain fields that are either protected or
        # are not present in the user db. If any key in the payload does not match
        # with the column name we will abort the update request.
        non_existent = set(post_data.keys()).difference(
            set(User.__table__.columns.keys())
        )
        if non_existent:
            self.logger.warning(
                "User trying to update fields that are not present in the user database. Fields: {}",
                non_existent,
            )
            abort(400, message="Invalid fields in update request payload")
        protected = set(post_data.keys()).intersection(set(User.get_protected()))
        for field in protected:
            if getattr(user, field) != post_data[field]:
                self.logger.warning(
                    "User trying to update the non-updatable fields. {}: {}",
                    field,
                    post_data[field],
                )
                abort(403, message="Invalid update request payload")
        try:
            user.update(**post_data)
        except Exception:
            self.logger.exception("Exception occurred during updating user object")
            abort(500, message="INTERNAL ERROR")

        response_object = {
            "message": "success",
            "data": user.get_json(),
        }
        return make_response(jsonify(response_object), 200)

    @Auth.token_auth.login_required()
    def delete(self, username):
        """
        Delete request for deleting a user from database.
        This requires a Pbench auth token in the header field

        Required headers include

            Content-Type:   application/json
            Accept:         application/json
            Authorization:   Bearer Pbench_auth_token (user received upon login)

        :return: JSON Payload
            response_object = {
                    "message": "Successfully deleted."/"failure message",
                }
        """
        try:
            user, verified = self.auth.verify_user(username)
        except Exception:
            self.logger.exception("Exception occurred during the getUser {}", username)
            abort(500, message="INTERNAL ERROR")

        # TODO: Check if the user has the right privileges
        if not verified and not user.is_admin():
            self.logger.warning(
                "User {} is not authorized to delete user {}.", user.username, username,
            )
            abort(403, message="Not authorized to delete user")

        try:
            user = User.query(username=username)
            # Do not delete if the user is admin
            if not user.is_admin():
                User.delete(username)
        except Exception:
            self.logger.exception(
                "Exception occurred during deleting the user entry for user '{}'",
                username,
            )
            abort(500, message="INTERNAL ERROR")
        else:
            if user.is_admin():
                self.logger.warning("Admin attempted to delete admin user")
                abort(403, message="Admin user can not be deleted")
            self.logger.info("User entry deleted for user with username {}", username)

        response_object = {
            "message": "Successfully deleted.",
        }
        return make_response(jsonify(response_object), 200)
