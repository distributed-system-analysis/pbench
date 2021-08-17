import datetime
import jwt
import os

from http import HTTPStatus
from flask import abort, request
from flask_httpauth import HTTPTokenAuth

from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.database.models.users import User


class UnknownUser(Exception):
    """
    UnknownUser Attempt to validate a user that doesn't exist.
    """

    def __init__(self, username: str):
        self.username = username

    def __str__(self):
        return f"No such user {self.username}"


class Auth:
    token_auth = HTTPTokenAuth("Bearer")

    @staticmethod
    def set_logger(logger):
        # Logger gets set at the time of auth module initialization
        Auth.logger = logger

    @staticmethod
    def validate_user(name: str) -> str:
        """
        Encapsulate a query to reject "username" values that don't correspond to
        a registered user. A valid username is translated to the internal
        representation for Elasticsearch indexing, which is the stringified
        user ID number.

        Args:
            name: The username field of a registered user

        Raises:
            ValueError: The username doesn't correspond to a registered user
            TypeError: Some other error occurred looking for the user

        Returns:
            The user's ID value (as a string)
        """
        try:
            user = User.query(username=name)
        except Exception:
            User.logger.exception("Unexpected exception from query for user {}", name)
            raise
        if not user:
            raise UnknownUser(name)
        return str(user.id)

    def encode_auth_token(self, token_expire_duration, user_id):
        """
        Generates the Auth Token
        :return: jwt token string
        """
        current_utc = datetime.datetime.utcnow()
        payload = {
            "iat": current_utc,
            "exp": current_utc + datetime.timedelta(minutes=int(token_expire_duration)),
            "sub": user_id,
        }

        # Get jwt key
        jwt_key = self.get_secret_key()
        return jwt.encode(payload, jwt_key, algorithm="HS256")

    def get_secret_key(self):
        try:
            return os.getenv("SECRET_KEY", "my_precious")
        except Exception as e:
            Auth.logger.exception(f"{__name__}: ERROR: {e.__traceback__}")

    def verify_user(self, target_username: str) -> User:
        """
        Check whether the requested target user is the owner of the authorization
        token provided to the API.

        We're returning a User instance corresponding to the target username provided.
        If the request is not authenticated (current user is None) we return None as
        we won't be able to verify the target user. However, if the current user is
        an admin, we return the instance of the target user by querying the target
        username provided.
        """
        current_user = Auth.token_auth.current_user()
        if not current_user:
            return None
        if current_user.username == target_username:
            return current_user
        if current_user.is_admin():
            target_user = User.query(username=target_username)
            return target_user
        return None

    def get_auth_token(self, logger):
        # get auth token
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            logger.warning("Missing expected Authorization header")
            abort(
                HTTPStatus.FORBIDDEN,
                message="Please add 'Authorization' token as Authorization: Bearer <session_token>",
            )

        try:
            auth_schema, auth_token = auth_header.split()
        except ValueError:
            logger.warning("Malformed Auth header")
            abort(
                HTTPStatus.UNAUTHORIZED,
                message="Malformed Authorization header, please add request header as Authorization: Bearer <session_token>",
            )
        else:
            if auth_schema.lower() != "bearer":
                logger.warning(
                    "Expected authorization schema to be 'bearer', not '{}'",
                    auth_schema,
                )
                abort(
                    HTTPStatus.UNAUTHORIZED,
                    message="Malformed Authorization header, request needs bearer token: Bearer <session_token>",
                )
            return auth_token

    @staticmethod
    @token_auth.verify_token
    def verify_auth(auth_token):
        """
        Validates the auth token
        :param auth_token:
        :return: User object/None
        """
        try:
            payload = jwt.decode(
                auth_token, os.getenv("SECRET_KEY", "my_precious"), algorithms="HS256",
            )
            user_id = payload["sub"]
            if ActiveTokens.valid(auth_token):
                user = User.query(id=user_id)
                return user
        except jwt.ExpiredSignatureError:
            try:
                ActiveTokens.delete(auth_token)
            except Exception:
                Auth.logger.error(
                    "User attempted Pbench expired token but we could not delete the expired auth token from the database. token: '{}'",
                    auth_token,
                )
                return None
            Auth.logger.warning(
                "User attempted Pbench expired token '{}', Token deleted from the database and no longer tracked",
                auth_token,
            )
        except jwt.InvalidTokenError:
            Auth.logger.warning("User attempted invalid Pbench token '{}'", auth_token)
        except Exception:
            Auth.logger.exception(
                "Exception occurred while verifying the auth token '{}'", auth_token
            )
        return None