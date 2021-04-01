import jwt
import os
import datetime
from flask import request, abort
from flask_httpauth import HTTPTokenAuth
from pbench.server.database.models.users import User
from pbench.server.database.models.active_tokens import ActiveTokens


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
        a registered user.

        TODO: We need to decide exactly how we're representing our users, and
        what's mutable. For example, if we allow changing "username" we need to
        have a stable "userid" field that we use for indexing... in which case
        this should translate "username" into "userid" for internal use. For
        now, just return the original username if it was found.

        FIXME: I thought this would be an ArgumentParser "type" so we could
        do validation during parsing. That's awkward because we need to finish
        parsing the --config parameter in order to access the config and logger
        objects required to initialize database access, which needs to be done
        before we can make a query. Can we work around this without too much
        mess?

        Args:
            :name: The username field of a registered user

        Raises:
            ValueError: The username doesn't correspond to a registered user
            TypeError: Some other error occurred looking for the user

        Returns:
            The specified username if it's valid; does not return on failure
        """
        try:
            user = User.query(username=name)
        except Exception:
            User.logger.exception("Unexpected exception from query for user {}", name)
            raise
        if not user:
            raise UnknownUser(name)
        return name

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

    def verify_user(self, username):
        """
        Check if the provided username belongs to the current user by
        querying the Usermodel with the current user
        :param username:
        :param logger
        :return: User (UserModel instance), verified status (boolean)
        """
        user = User.query(id=self.token_auth.current_user().id)
        # check if the current username matches with the one provided
        verified = user is not None and user.username == username
        Auth.logger.warning("verified status of user '{}' is '{}'", username, verified)

        return user, verified

    def get_auth_token(self, logger):
        # get auth token
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            logger.warning("Missing expected Authorization header")
            abort(
                403,
                message="Please add 'Authorization' token as Authorization: Bearer <session_token>",
            )

        try:
            auth_schema, auth_token = auth_header.split()
        except ValueError:
            logger.warning("Malformed Auth header")
            abort(
                401,
                message="Malformed Authorization header, please add request header as Authorization: Bearer <session_token>",
            )
        else:
            if auth_schema.lower() != "bearer":
                logger.warning(
                    "Expected authorization schema to be 'bearer', not '{}'",
                    auth_schema,
                )
                abort(
                    401,
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
