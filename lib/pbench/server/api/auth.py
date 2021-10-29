import datetime
import os

from flask import abort, request
from flask_httpauth import HTTPTokenAuth
from http import HTTPStatus
import jwt

from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.database.models.users import User


class Auth:
    token_auth = HTTPTokenAuth("Bearer")

    @staticmethod
    def set_logger(logger):
        # Logger gets set at the time of auth module initialization
        Auth.logger = logger

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
            Auth.logger.exception("Error {} getting JWT secret", e)

    def get_auth_token(self, logger):
        # get auth token
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            abort(
                HTTPStatus.FORBIDDEN,
                message="Please add authorization token as 'Authorization: Bearer <session_token>'",
            )

        try:
            auth_schema, auth_token = auth_header.split()
        except ValueError:
            abort(
                HTTPStatus.UNAUTHORIZED,
                message="Malformed Authorization header, please add request header as Authorization: Bearer <session_token>",
            )
        else:
            if auth_schema.lower() != "bearer":
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
            except Exception as e:
                Auth.logger.error(
                    "User passed expired token but we could not delete the token from the database. token: {!r}: {}",
                    auth_token,
                    e,
                )
        except jwt.InvalidTokenError:
            pass  # Ignore this silently; client is unauthenticated
        except Exception as e:
            Auth.logger.exception(
                "Unexpected exception occurred while verifying the auth token {!r}: {}",
                auth_token,
                e,
            )
        return None
