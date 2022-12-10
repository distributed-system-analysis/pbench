import datetime
from http import HTTPStatus
from logging import Logger
import os
from typing import Optional

from flask import current_app, request
from flask_httpauth import HTTPTokenAuth
from flask_restful import abort
import jwt

from pbench.server.auth import OpenIDClient, OpenIDClientError
from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.database.models.users import User


class Auth:
    token_auth = HTTPTokenAuth("Bearer")
    secret_key = ""

    @staticmethod
    def set_logger(logger):
        # Logger gets set at the time of auth module initialization
        Auth.logger = logger

    @staticmethod
    def get_user_id() -> Optional[str]:
        """
        Returns the user id of the current authenticated user.
        If the user not authenticated this would return None
        """
        user_id = None
        user = Auth.token_auth.current_user()
        if user:
            user_id = str(user.id)
        return user_id

    @staticmethod
    def _get_secret_key():
        if not Auth.secret_key:
            Auth.secret_key = os.getenv("SECRET_KEY", "my_precious")
        return Auth.secret_key

    def encode_auth_token(self, time_delta: datetime.timedelta, user_id: int) -> str:
        """
        Generates the Auth Token
        Args:
            time_delta: Token lifetime
            user_id: Authorized user's internal ID
        Returns:
            JWT token string
        """
        current_utc = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "iat": current_utc,
            "exp": current_utc + time_delta,
            "sub": user_id,
        }

        # Get jwt key
        jwt_key = Auth._get_secret_key()
        return jwt.encode(payload, jwt_key, algorithm="HS256")

    def get_auth_token(self):
        # get auth token
        example = (
            "Please add Authorization header with Bearer token as,"
            " 'Authorization: Bearer <session_token>'"
        )
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            abort(
                HTTPStatus.FORBIDDEN,
                message=f"No Authorization header provided.  {example}",
            )

        try:
            auth_schema, auth_token = auth_header.split(" ", 1)
        except ValueError:
            abort(
                HTTPStatus.UNAUTHORIZED,
                message=f"Malformed Authorization header.  {example}",
            )
        else:
            if auth_schema.lower() != "bearer":
                abort(
                    HTTPStatus.UNAUTHORIZED,
                    message=f"Malformed Authorization header.  {example}",
                )
            return auth_token

    @staticmethod
    @token_auth.verify_token
    def verify_auth(auth_token):
        """
        Validates the auth token.
        Note: Since we are not encoding 'aud' claim in our JWT tokens
        we need to set 'verify_aud' to False while validating the token.
        :param auth_token:
        :return: User object/None
        """
        try:
            payload = jwt.decode(
                auth_token,
                Auth._get_secret_key(),
                algorithms="HS256",
                options={
                    "verify_signature": True,
                    "verify_aud": False,
                    "verify_exp": True,
                },
            )
            user_id = payload["sub"]
            if ActiveTokens.valid(auth_token):
                user = User.query(id=user_id)
                return user
        except jwt.ExpiredSignatureError:
            try:
                ActiveTokens.delete(auth_token)
            except Exception as e:
                current_app.logger.error(
                    "User passed expired token but we could not delete the token from the database. token: {!r}: {}",
                    auth_token,
                    e,
                )
        except jwt.InvalidTokenError:
            pass  # Ignore this silently; client is unauthenticated
        except Exception as e:
            current_app.logger.exception(
                "Unexpected exception occurred while verifying the auth token {!r}: {}",
                auth_token,
                e,
            )
        return None

    @staticmethod
    def verify_third_party_token(
        auth_token: str, oidc_client: OpenIDClient, logger: Logger
    ) -> bool:
        """
        Verify a token provided to the Pbench server which was obtained from a
        third party identity provider.
        Args:
            auth_token: Token to authenticate
            oidc_client: OIDC client to call to authenticate the token
        Returns:
            True if the verification succeeds else False
        """
        try:
            oidc_client.token_introspect_offline(
                token=auth_token,
                key=oidc_client.get_oidc_public_key(),
                audience=oidc_client.client_id,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_exp": True,
                },
            )
            return True
        except (
            jwt.ExpiredSignatureError,
            jwt.InvalidTokenError,
            jwt.InvalidAudienceError,
        ):
            logger.error("OIDC token verification failed")
            return False
        except Exception:
            logger.exception(
                "Unexpected exception occurred while verifying the auth token {}",
                auth_token,
            )

        if not oidc_client.TOKENINFO_ENDPOINT:
            logger.warning("Can not perform OIDC online token verification")
            return False

        try:
            token_payload = oidc_client.token_introspect_online(
                token=auth_token, token_info_uri=oidc_client.TOKENINFO_ENDPOINT
            )
        except OpenIDClientError:
            return False

        return "aud" in token_payload and oidc_client.client_id in token_payload["aud"]
