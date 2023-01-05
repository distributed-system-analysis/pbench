from dataclasses import dataclass
import datetime
from http import HTTPStatus
import os
from typing import Optional, Union

from flask import request
from flask_httpauth import HTTPTokenAuth
from flask_restful import abort
import jwt

from pbench.server import PbenchServerConfig
from pbench.server.auth import OpenIDClient, OpenIDClientError
from pbench.server.database.models.active_tokens import ActiveTokens
from pbench.server.database.models.users import User


@dataclass
class InternalUser:
    """Internal user class for storing user related fields fetched
    from OIDC token decode.

    Note: Class attributes are duck-typed from the SQL User object,
    and they need to match with the respective sql entry!
    """

    id: str
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    roles: Optional[list[str]] = None

    def __str__(self) -> str:
        return f"User, id: {self.id}, username: {self.username}"

    def is_admin(self):
        return "ADMIN" in self.roles

    @classmethod
    def create(cls, client_id: str, token_payload: dict) -> "InternalUser":
        """Helper method to return the Internal User object

        Args:
            client_id: authorized client id string
            token_payload: Dict representation of decoded token
        Returns:
             InternalUser object
        """
        roles = []
        audiences = token_payload.get("resource_access", {})
        if client_id in audiences:
            roles = audiences[client_id].get("roles", [])
        return cls(
            id=token_payload["sub"],
            username=token_payload.get("preferred_username"),
            email=token_payload.get("email"),
            first_name=token_payload.get("given_name"),
            last_name=token_payload.get("family_name"),
            roles=roles,
        )


class Auth:
    token_auth = HTTPTokenAuth("Bearer")
    oidc_client: OpenIDClient = None

    @staticmethod
    def set_logger(logger):
        # Logger gets set at the time of auth module initialization
        Auth.logger = logger

    @staticmethod
    def set_oidc_client(server_config: PbenchServerConfig):
        """OIDC client initialization for third party token verification

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
    def verify_auth(auth_token: str) -> Optional[Union[User, InternalUser]]:
        """
        Validates the auth token.

        :param auth_token:
        :return: User object/None

        Args:
            auth_token: Authentication token string
        Returns:
            User object, InternalUser object, or None
        """
        if Auth.oidc_client and not Auth.oidc_client.USERINFO_ENDPOINT:
            Auth.oidc_client.set_well_known_endpoints()
        try:
            payload = jwt.decode(
                auth_token,
                Auth().get_secret_key(),
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
            Auth.logger.debug(
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
        algorithms: Optional[list[str]] = None,
    ) -> Optional[InternalUser]:
        """
        Verify a token provided to the Pbench server which was obtained from a
        third party identity provider.
        Args:
            auth_token: Token to authenticate
            oidc_client: OIDC client to call to authenticate the token
            algorithms: Optional token signature algorithm argument,
                        defaults to HS256
        Returns:
            InternalUser object if the verification succeeds else None
        """
        try:
            identity_provider_pubkey = oidc_client.get_oidc_public_key(auth_token)
        except Exception:
            Auth.logger.info("Identity provider public key fetch failed")
            identity_provider_pubkey = Auth().get_secret_key()
        try:
            token_payload = oidc_client.token_introspect_offline(
                token=auth_token,
                key=identity_provider_pubkey,
                audience=oidc_client.client_id,
                algorithms=["HS256"] if not algorithms else algorithms,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_exp": True,
                },
            )
        except (
            jwt.ExpiredSignatureError,
            jwt.InvalidTokenError,
            jwt.InvalidAudienceError,
        ):
            return None
        except Exception:
            Auth.logger.exception(
                "Unexpected exception occurred while verifying the auth token {}",
                auth_token,
            )

            # If offline token verification results in some unexpected errors,
            # we will perform the online token verification.
            # Note: Online verification should NOT be performed frequently, and
            # it is only allowed for non-public clients.
            if not oidc_client.TOKENINFO_ENDPOINT:
                Auth.logger.debug("Can not perform OIDC online token verification")
                return None

            try:
                token_payload = oidc_client.token_introspect_online(
                    token=auth_token, token_info_uri=oidc_client.TOKENINFO_ENDPOINT
                )
                if oidc_client.client_id not in token_payload.get("aud"):
                    # If our client is not an intended audience for the token,
                    # we will not verify the token.
                    return None
            except OpenIDClientError:
                return None
        return InternalUser.create(
            client_id=oidc_client.client_id, token_payload=token_payload
        )
