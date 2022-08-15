import datetime
from http import HTTPStatus
import os

from flask import abort, request
from flask_httpauth import HTTPTokenAuth
import jwt

from pbench.server.auth import OpenIDClient
from pbench.server.auth.exceptions import OpenIDClientError
from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.database.models.users import User


class Auth:
    token_auth = HTTPTokenAuth("Bearer")

    @staticmethod
    def set_logger(logger):
        # Logger gets set at the time of auth module initialization
        Auth.logger = logger

    def encode_auth_token(self, time_delta: datetime.timedelta, user_id: int) -> str:
        """
        Generates the Auth Token
        Args:
            time_delta: Token lifetime
            user_id: Authorized user's internal ID
        Returns:
            JWT token string
        """
        current_utc = datetime.datetime.utcnow()
        payload = {
            "iat": current_utc,
            "exp": current_utc + time_delta,
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
                auth_token,
                os.getenv("SECRET_KEY", "my_precious"),
                algorithms="HS256",
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

    @staticmethod
    def verify_third_party_token(
        auth_token: str, oidc_client: OpenIDClient, tokeninfo_endpoint: str = None
    ) -> bool:
        """
        Verify a token provided to the Pbench server which was obtained from a
        third party identity provider.
        Args:
            auth_token: Token to authenticate
            oidc_client: OIDC client to call to authenticate the token
            tokeninfo_endpoint: Optional tokeninfo_endpoint to validate
                                tokens online in case offline verification
                                results in some exception.
        Returns:
            True if the verification succeed else False
        """
        # Verify auth token validity
        identity_provider_pubkey = oidc_client.get_oidc_public_key(auth_token)
        try:
            oidc_client.token_introspect_offline(
                token=auth_token,
                key=identity_provider_pubkey,
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
            Auth.logger.error("oidc token verification failed")
        except Exception as e:
            Auth.logger.exception(
                "Unexpected exception occurred while verifying the auth token {}: {}",
                auth_token,
                e,
            )
            if not tokeninfo_endpoint:
                Auth.logger.warning("Can not perform oidc online token verification")
            else:
                try:
                    token_payload = oidc_client.token_introspect_online(
                        token=auth_token, token_info_uri=tokeninfo_endpoint
                    )
                    if "aud" not in token_payload:
                        return False
                    elif oidc_client.client_id in token_payload["aud"]:
                        # If our client is an intended audience then only we accept the token
                        return True
                except OpenIDClientError:
                    return False
        return False
