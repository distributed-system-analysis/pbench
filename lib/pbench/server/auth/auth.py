import datetime
import enum
from http import HTTPStatus
from logging import Logger
from typing import Optional, Tuple

from flask import current_app, Flask, request
from flask_httpauth import HTTPTokenAuth
from flask_restful import abort
import jwt

from pbench.server import PbenchServerConfig
from pbench.server.auth import OpenIDClient, OpenIDClientError
from pbench.server.database.models.active_token import ActiveToken
from pbench.server.database.models.user import User

# Module private constants
_TOKEN_ALG = "HS256"

# Module public
token_auth = HTTPTokenAuth("Bearer")


def setup_app(app: Flask, server_config: PbenchServerConfig):
    """Setup the given Flask app from the given Pbench Server configuration
    object.

    Sets the Flask apps `secret_key` attribute to the configured "secret-key"
    value in the Pbench Server "authentication" section.

    Args:

        app           : The target Flask application to setup
        server_config : The Pbench Server configuration to use
    """
    app.secret_key = server_config._get_conf("authentication", "secret-key")


def get_current_user_id() -> Optional[str]:
    """Returns the user id of the current authenticated user.
    If the user is not authenticated returns None
    """
    user_id = None
    user = token_auth.current_user()
    if user:
        user_id = str(user.id)
    return user_id


def encode_auth_token(
    time_delta: datetime.timedelta, user_id: int
) -> Tuple[str, datetime.datetime]:
    """Generates the Auth Token

    Args:
        time_delta : Token lifetime
        user_id    : Authorized user's internal ID

    Returns:
        JWT token string, expiration
    """
    current_utc = datetime.datetime.now(datetime.timezone.utc)
    expiration = current_utc + time_delta
    payload = {
        "iat": current_utc,
        "exp": expiration,
        "sub": user_id,
    }

    return jwt.encode(payload, current_app.secret_key, algorithm=_TOKEN_ALG), expiration


def get_auth_token():
    """Get the bearer token from the Authorization header of the current request
    in flight.

    Will `abort()` the request if the token is not found reporting the reason.
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


class TokenState(enum.Enum):
    """The state of a token once decoded."""

    INVALID = enum.auto()
    EXPIRED = enum.auto()
    VERIFIED = enum.auto()


def verify_token_only(auth_token: str) -> TokenState:
    """Returns a TokenState depending on the state of the given token after
    being decoded.

    Args:
        auth_token : the authorization token to verify

    Returns:
        The TokenState enumeration for the decode operation
    """
    try:
        jwt.decode(
            auth_token,
            current_app.secret_key,
            algorithms=_TOKEN_ALG,
            options={
                "verify_signature": True,
                "verify_aud": False,
                "verify_exp": True,
            },
        )
    except jwt.InvalidTokenError:
        state = TokenState.INVALID
    except jwt.ExpiredSignatureError:
        state = TokenState.EXPIRED
    else:
        state = TokenState.VERIFIED
    return state


@token_auth.verify_token
def verify_auth(auth_token: str) -> Optional[User]:
    """For APIs requiring a valid token to operate, the token must not only be
    valid as decoded, but also be associated with a user in the database.

    Note: Since we are not encoding 'aud' claim in our JWT tokens we need to
    set 'verify_aud' to False while validating the token.

    Args:
        auth_token : the authorization token to verify

    Returns
        The User database object associated with the token if the token is
        valid, otherwise None
    """
    state = verify_token_only(auth_token)
    if state == TokenState.VERIFIED:
        token = ActiveToken.query(auth_token)
        user = token.user if token else None
    else:
        user = None
    return user


def verify_third_party_token(
    auth_token: str, oidc_client: OpenIDClient, logger: Logger
) -> bool:
    """Verify a token provided to the Pbench server which was obtained from a
    third party identity provider.

    Args:
        auth_token  : Token to authenticate
        oidc_client : OIDC client to call to authenticate the token

    Returns:
        True if the verification succeeds else False
    """
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
