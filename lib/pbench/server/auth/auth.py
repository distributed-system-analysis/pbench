import datetime
from http import HTTPStatus
import os
from typing import Optional

from flask import request
from flask_httpauth import HTTPTokenAuth
from flask_restful import abort
import jwt

from pbench.server import PbenchServerConfig
from pbench.server.auth import OpenIDClient, OpenIDClientError
from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.database.models.users import User


class InternalUser:
    """
    Internal user class for storing user related fields fetched
    from OIDC token decode.
    """

    def __init__(
        self,
        id: str,
        username: str,
        email: str,
        first_name: str = None,
        last_name: str = None,
        roles: list[str] = None,
    ):
        self.id = id
        self.username = username
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.roles = roles

    def __str__(self):
        return f"User, id: {self.id}, username: {self.username}"

    def is_admin(self):
        return "ADMIN" in self.roles


class Auth:
    token_auth = HTTPTokenAuth("Bearer")
    oidc_client: OpenIDClient = None

    @staticmethod
    def set_logger(logger):
        # Logger gets set at the time of auth module initialization
        Auth.logger = logger

    @staticmethod
    def set_oidc_client(server_config: PbenchServerConfig):
        """
        OIDC client initialization for third party token verification
        Args:
            server_config: Parsed Pbench server configuration
        """
        server_url = server_config.get(
            "authentication",
            "internal_server_url",
            fallback=server_config.get("authentication", "server_url"),
        )
        client = server_config.get("authentication", "client")
        realm = server_config.get("authentication", "realm")
        secret = server_config.get("authentication", "secret", fallback=None)
        Auth.oidc_client = OpenIDClient(
            server_url=server_url,
            client_id=client,
            logger=Auth.logger,
            realm_name=realm,
            client_secret_key=secret,
            verify=False,
        )

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
        jwt_key = self.get_secret_key()
        return jwt.encode(payload, jwt_key, algorithm="HS256")

    def get_secret_key(self):
        try:
            return os.getenv("SECRET_KEY", "my_precious")
        except Exception as e:
            Auth.logger.exception("Error {} getting JWT secret", e)

    def get_auth_token(self, logger):
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
        if not Auth.oidc_client.USERINFO_ENDPOINT:
            Auth.oidc_client.set_well_known_endpoints()
        try:
            payload = jwt.decode(
                auth_token,
                os.getenv("SECRET_KEY", "my_precious"),
                algorithms="HS256",
                options={
                    "verify_signature": True,
                    "verify_aud": True,
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
                Auth.logger.error(
                    "User passed expired token but we could not delete the token from the database. token: {!r}: {}",
                    auth_token,
                    e,
                )
        except jwt.InvalidTokenError:
            Auth.logger.warning(
                "Internal token verification failed, trying OIDC token verification"
            )
            return Auth.verify_third_party_token(auth_token, Auth.oidc_client)
        except Exception as e:
            Auth.logger.exception(
                "Unexpected exception occurred while verifying the auth token {!r}: {}",
                auth_token,
                e,
            )
        return None

    @staticmethod
    def verify_third_party_token(
        auth_token: str,
        oidc_client: OpenIDClient,
        algorithms: Optional[list[str]] = ["HS256"],
    ) -> "InternalUser":
        """
        Verify a token provided to the Pbench server which was obtained from a
        third party identity provider.
        Args:
            auth_token: Token to authenticate
            oidc_client: OIDC client to call to authenticate the token
            algorithms: Optional token signature algorithm argument,
                        defaults to HS256
        Returns:
            True if the verification succeeds else False
        """
        try:
            identity_provider_pubkey = oidc_client.get_oidc_public_key(auth_token)
        except Exception:
            Auth.logger.warning("Identity provider public key fetch failed")
            identity_provider_pubkey = Auth().get_secret_key()
        try:
            audience = oidc_client.client_id if oidc_client else None
            token_decode = oidc_client.token_introspect_offline(
                token=auth_token,
                key=identity_provider_pubkey,
                audience=audience,
                algorithms=algorithms,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_exp": True,
                },
            )
            roles = []
            if audience in token_decode.get("resource_access"):
                roles = token_decode.get("resource_access").get(audience).get("roles")
            return InternalUser(
                id=token_decode.get("sub"),
                username=token_decode.get("preferred_username"),
                email=token_decode.get("email"),
                first_name=token_decode.get("given_name"),
                last_name=token_decode.get("family_name"),
                roles=roles,
            )
        except (
            jwt.ExpiredSignatureError,
            jwt.InvalidTokenError,
            jwt.InvalidAudienceError,
        ):
            Auth.logger.warning("OIDC token verification failed")
            return None
        except Exception:
            Auth.logger.exception(
                "Unexpected exception occurred while verifying the auth token {}",
                auth_token,
            )

        if not oidc_client.TOKENINFO_ENDPOINT:
            Auth.logger.warning("Can not perform OIDC online token verification")
            return None

        try:
            token_payload = oidc_client.token_introspect_online(
                token=auth_token, token_info_uri=oidc_client.TOKENINFO_ENDPOINT
            )
        except OpenIDClientError:
            return None

        return "aud" in token_payload and oidc_client.client_id in token_payload["aud"]
