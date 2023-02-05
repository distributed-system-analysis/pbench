from datetime import datetime, timedelta, timezone
import enum
from http import HTTPStatus
from typing import Optional, Tuple, Union

from flask import current_app, Flask, request
from flask_httpauth import HTTPTokenAuth
from flask_restful import abort
import jwt

from pbench.server import PbenchServerConfig
from pbench.server.auth import (
    InternalUser,
    OpenIDClient,
    OpenIDClientError,
    OpenIDTokenInvalid,
)
from pbench.server.database.models.auth_tokens import AuthToken
from pbench.server.database.models.users import User

# Module private constants
_TOKEN_ALG_INT = "HS256"

# Module public
token_auth = HTTPTokenAuth("Bearer")
oidc_client: OpenIDClient = None


def setup_app(app: Flask, server_config: PbenchServerConfig):
    """Setup the given Flask app from the given Pbench Server configuration
    object.

    Sets the Flask apps `secret_key` attribute to the configured "secret-key"
    value in the Pbench Server "flask-app" section.

    We attempt to construct an OpenID Client object for third party token
    verification if the configuration is provided.

    Args:
        server_config : Parsed Pbench server configuration
    """
    app.secret_key = server_config.get("flask-app", "secret-key")

    global oidc_client
    try:
        oidc_client = OpenIDClient.construct_oidc_client(server_config)
    except OpenIDClient.NotConfigured:
        oidc_client = None


def get_current_user_id() -> Optional[str]:
    """Return the user ID associated with the authentication token.

    Returns:
        User ID of the authenticated user, None otherwise.
    """
    user = token_auth.current_user()
    return str(user.id) if user else None


def encode_auth_token(time_delta: timedelta, user_id: int) -> Tuple[str, datetime]:
    """Generates an authorization token for an internal user ID.

    Args:
        time_delta : Token lifetime
        user_id : Authorized user's internal ID

    Returns:
        JWT token string, expiration
    """
    current_utc = datetime.now(timezone.utc)
    expiration = current_utc + time_delta
    payload = {
        "iat": current_utc,
        "exp": expiration,
        "sub": user_id,
    }
    try:
        auth_token = jwt.encode(
            payload, current_app.secret_key, algorithm=_TOKEN_ALG_INT
        )
    except (
        jwt.InvalidIssuer,
        jwt.InvalidIssuedAtError,
        jwt.InvalidAlgorithmError,
        jwt.PyJWTError,
    ):
        current_app.logger.exception(
            "Could not encode the JWT auth token for user ID: {}", user_id
        )
        abort(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message="INTERNAL ERROR",
        )
    return auth_token, expiration


def get_auth_token() -> str:
    """Get the authorization token from the current request.

    Returns:
        The bearer token extracted from the authorization header
    """
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


@token_auth.verify_token
def verify_auth(auth_token: str) -> Optional[Union[User, InternalUser]]:
    """Validates the auth token of the current request.

    If an OpenID Connect client is configured, then actual token verification
    is performed by the OpenID Connect version, otherwise our internal version
    is used.

    Args:
        auth_token : authorization token string

    Returns:
        None if the token is not valid, a `User` object when the token is
        an internally generated one, and an `InternalUser` object when the
        token is validated using the OpenID Connect client.
    """
    if not auth_token:
        return None
    user = None
    try:
        if oidc_client is not None:
            user = verify_auth_oidc(auth_token)
        else:
            user = verify_auth_internal(auth_token)
    except Exception as e:
        current_app.logger.exception(
            "Unexpected exception occurred while verifying the auth token {!r}: {}",
            auth_token,
            e,
        )
    return user


class TokenState(enum.Enum):
    """The state of a token once decoded."""

    INVALID = enum.auto()
    EXPIRED = enum.auto()
    VERIFIED = enum.auto()


def verify_internal_token(auth_token: str) -> TokenState:
    """Returns a TokenState depending on the state of the given token after
    being decoded.
    """
    try:
        jwt.decode(
            auth_token,
            current_app.secret_key,
            algorithms=_TOKEN_ALG_INT,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True,
            },
        )
    except (jwt.InvalidSignatureError, jwt.DecodeError):
        state = TokenState.INVALID
    except jwt.ExpiredSignatureError:
        state = TokenState.EXPIRED
    else:
        state = TokenState.VERIFIED
    return state


def verify_auth_internal(auth_token_s: str) -> Optional[User]:
    """Validates the auth token of the current request.

    Tries to validate the token as if it was generated by the Pbench server for
    an internal user.

    Args:
        auth_token_s : authorization token string

    Returns:
        None if the token is not valid, a `User` object when the token is valid.
    """
    state = verify_internal_token(auth_token_s)
    if state == TokenState.VERIFIED:
        auth_token = AuthToken.query(auth_token_s)
        user = auth_token.user if auth_token else None
    else:
        user = None
    return user


def verify_auth_oidc(auth_token: str) -> Optional[InternalUser]:
    """Verify a token provided to the Pbench server which was obtained from a
    third party identity provider.

    Args:
        auth_token : Token to authenticate

    Returns:
        InternalUser object if the verification succeeds, None on failure.
    """
    try:
        token_payload = oidc_client.token_introspect_offline(token=auth_token)
    except OpenIDTokenInvalid:
        token_payload = None
    except Exception:
        current_app.logger.exception(
            "Unexpected exception occurred while verifying the auth token {}",
            auth_token,
        )

        # Offline token verification resulted in some unexpected error,
        # perform the online token verification.

        # Note: Online verification should NOT be performed frequently, and it
        # is only allowed for non-public clients.
        try:
            token_payload = oidc_client.token_introspect_online(token=auth_token)
        except OpenIDClientError as exc:
            current_app.logger.debug(
                "Can not perform OIDC online token verification, '{}'", exc
            )
            token_payload = None

    return (
        None
        if token_payload is None
        else InternalUser.create(
            # FIXME - `client_id` is the value pulled from the Pbench Server
            # "openid-connect" "client" field in the configuration file.  This
            # needs to be an ID from the OpenID Connect response payload (online
            # case) or decoded token (offline case).
            client_id=oidc_client.client_id,
            token_payload=token_payload,
        )
    )
