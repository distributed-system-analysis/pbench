import datetime
from http import HTTPStatus
from typing import Optional, Union

from flask import current_app, Flask, request
from flask_httpauth import HTTPTokenAuth
from flask_restful import abort
import jwt

from pbench.server import PbenchServerConfig
from pbench.server.auth import InternalUser, OpenIDClient, OpenIDTokenInvalid
from pbench.server.database.models.active_tokens import ActiveTokens
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


def encode_auth_token(time_delta: datetime.timedelta, user_id: int) -> str:
    """Generates an authorization token for an internal user ID.

    Args:
        time_delta : Token lifetime
        user_id : Authorized user's internal ID

    Returns:
        JWT token string
    """
    current_utc = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "iat": current_utc,
        "exp": current_utc + time_delta,
        "sub": user_id,
    }
    return jwt.encode(payload, current_app.secret_key, algorithm=_TOKEN_ALG_INT)


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


def verify_auth_internal(auth_token: str) -> Optional[User]:
    """Validates the auth token of the current request.

    Tries to validate the token as if it was generated by the Pbench server for
    an internal user.

    Args:
        auth_token : authorization token string

    Returns:
        None if the token is not valid, a `User` object when the token is valid.
    """
    user = None
    try:
        payload = jwt.decode(
            auth_token,
            current_app.secret_key,
            algorithms=_TOKEN_ALG_INT,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True,
            },
        )
    except jwt.InvalidSignatureError:
        pass
    except jwt.ExpiredSignatureError:
        try:
            ActiveTokens.delete(auth_token)
        except Exception as e:
            current_app.logger.error(
                "User passed expired token but we could not delete the"
                " token from the database. token: {!r}: {}",
                auth_token,
                e,
            )
    else:
        user_id = payload["sub"]
        if ActiveTokens.valid(auth_token):
            user = User.query(id=user_id)
    return user


def verify_auth_oidc(auth_token: str) -> Optional[InternalUser]:
    """Verify a token provided to the Pbench server which was obtained from a
    third party identity provider.

    Note: Upon token introspection if we get a valid token, we import the
    available user information from the token into our internal User database.

    Args:
        auth_token : Token to authenticate

    Returns:
        InternalUser object if the verification succeeds, None on failure.
    """
    user = None
    try:
        token_payload = oidc_client.token_introspect(token=auth_token)
    except OpenIDTokenInvalid:
        pass
    except Exception:
        current_app.logger.exception(
            "Unexpected exception occurred while verifying the auth token {}",
            auth_token,
        )
        pass
    else:
        user_id = token_payload["sub"]
        user = User.query(oidc_id=user_id)
        if not user:
            audiences = token_payload.get("resource_access", {})
            try:
                oidc_client_roles = audiences[oidc_client.client_id].get("roles", [])
            except KeyError:
                oidc_client_roles = []
            username = token_payload.get("preferred_username")
            profile = {
                User.USER: {
                    "email": token_payload.get("email"),
                    "first_name": token_payload.get("given_name"),
                    "last_name": token_payload.get("family_name"),
                },
                User.SERVER: {
                    "roles": oidc_client_roles,
                    "registered_on": datetime.datetime.now().strftime(
                        "%m/%d/%Y, %H:%M:%S"
                    ),
                },
            }
            user = User(oidc_id=user_id, username=username, profile=profile)
            user.add()

    return user
