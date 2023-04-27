from http import HTTPStatus
from typing import Optional

from flask import current_app, Flask, request
from flask_httpauth import HTTPTokenAuth
from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.auth import OpenIDClient, OpenIDTokenInvalid
from pbench.server.database.models.api_keys import APIKey
from pbench.server.database.models.users import User

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
def verify_auth(auth_token: str) -> Optional[User]:
    """Validates the auth token of the current request.

    If an OpenID Connect client is configured, then actual token verification
    is performed by the OpenID Connect version, otherwise our internal version
    is used.

    Args:
        auth_token : authorization token string

    Returns:
        None if the token is not valid, a `User` object when the
        token is validated using the OpenID Connect client.
    """
    if not auth_token:
        return None
    user = None
    try:
        user = verify_auth_oidc(auth_token)
    except Exception as e:
        current_app.logger.exception(
            "Unexpected exception occurred while verifying the auth token {!r}: {}",
            auth_token,
            e,
        )
    return user


def verify_auth_api_key(api_key: str) -> Optional[User]:
    """Tries to validate the api_key that is generated by the Pbench server .

    Args:
        api_key : authorization token string

    Returns:
        None if the api_key is not valid, a `User` object when the api_key is valid.

    """
    key = APIKey.query(api_key)
    return key.user if key else None


def verify_auth_oidc(auth_token: str) -> Optional[User]:
    """Authorization token verification function.

    The verification will pass either if the token is from a third-party OIDC
    identity provider or if the token is a Pbench Server API key.

    The function will first attempt to validate the token as an OIDC access token.
    If that fails, it will then attempt to validate it as a Pbench Server API key.

    If the token is a valid access token (and not if it is an API key),
    we will import its contents into the internal user database.

    Args:
        auth_token : Token to authenticate

    Returns:
        User object if the verification succeeds, None on failure.
    """
    try:
        token_payload = oidc_client.token_introspect(token=auth_token)
    except OpenIDTokenInvalid:
        # The token is not a valid access token, fall through.
        pass
    except Exception:
        current_app.logger.exception(
            "Unexpected exception occurred while verifying the auth token {}",
            auth_token,
        )
    else:
        # Extract what we want to cache from the access token
        user_id = token_payload["sub"]
        username = token_payload.get("preferred_username", user_id)
        audiences = token_payload.get("resource_access", {})
        pb_aud = audiences.get(oidc_client.client_id, {})
        roles = pb_aud.get("roles", [])

        # Create or update the user in our cache
        user = User.query(id=user_id)
        if not user:
            user = User(id=user_id, username=username, roles=roles)
            user.add()
        else:
            user.update(username=username, roles=roles)
        return user

    try:
        return verify_auth_api_key(auth_token)
    except Exception:
        current_app.logger.exception(
            "Unexpected exception occurred while verifying the API key {}",
            auth_token,
        )

    return None
