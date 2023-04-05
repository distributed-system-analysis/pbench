from datetime import datetime, timedelta, timezone
from http import HTTPStatus

from flask import current_app, jsonify, make_response
from flask.wrappers import Request, Response
from flask_restful import abort
import jwt
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiBase,
    ApiContext,
    ApiMethod,
    ApiParams,
    ApiSchema,
)
import pbench.server.auth.auth as Auth
from pbench.server.database.models.api_key import APIKey
from pbench.server.database.models.audit import OperationCode


def generate_key(time_delta: timedelta, user):
    user_obj = user.get_json()
    current_utc = datetime.now(timezone.utc)
    expiration = current_utc + time_delta
    payload = {
        "iat": current_utc,
        "exp": expiration,
        "user_id": user_obj["id"],
        "username": user_obj["username"],
        "audience": Auth.oidc_client.client_id,
    }
    try:
        generated_api_key = jwt.encode(
            payload, current_app.secret_key, algorithm=Auth._TOKEN_ALG_INT
        )
    except (
        jwt.InvalidIssuer,
        jwt.InvalidIssuedAtError,
        jwt.InvalidAlgorithmError,
        jwt.PyJWTError,
    ):
        current_app.logger.exception(
            "Could not encode the JWT api_key for user: {}", user
        )
        abort(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            message="INTERNAL ERROR",
        )
    return generated_api_key, current_utc, expiration


class GenerateKey(ApiBase):
    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.POST,
                OperationCode.CREATE,
                authorization=ApiAuthorizationType.NONE,
            ),
        )
        self.server_config = config

    def _post(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Post request for generating a new persistent API key.

        Required headers include

            Content-Type:   application/json
            Accept:         application/json

        :return:
            Success: 201 with empty payload
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        """
        user = Auth.token_auth.current_user()
        api_key_expire_duration = self.server_config.get(
            "openid", "api_key_expiration_duration"
        )

        if user:
            try:
                new_key, current_utc, expiration = generate_key(
                    time_delta=timedelta(minutes=int(api_key_expire_duration)),
                    user=user,
                )
                try:
                    key = APIKey(
                        api_key=new_key, created=current_utc, expiration=expiration
                    )
                    user.update(api_key=key)
                    current_app.logger.info(
                        "New API key registered for user {} and the api_key is {}",
                        user.username,
                        new_key,
                    )
                except IntegrityError:
                    current_app.logger.warning("Duplicate api_key got created")
                    raise APIAbort(
                        HTTPStatus.CONFLICT,
                        message="Duplicate api_key created",
                    )
                except SQLAlchemyError as e:
                    current_app.logger.error(
                        "SQLAlchemy Exception while generating an api_key for the user {}",
                        type(e),
                    )
                    raise APIAbort(
                        HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR"
                    )
                except Exception:
                    current_app.logger.exception(
                        "Exception while updating an api_key for the user"
                    )
                    raise APIAbort(
                        HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR"
                    )

                response_object = {
                    "api_key": new_key,
                    "username": user.username,
                }
                return make_response(jsonify(response_object), HTTPStatus.OK)
            except Exception:
                current_app.logger.exception(
                    "Exception occurred while creating a generating an api_key"
                )
                abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        else:
            current_app.logger.info(
                "User provided access_token is invalid or expired token"
            )
            raise APIAbort(
                HTTPStatus.UNAUTHORIZED,
                "User provided access_token is invalid or expired token",
            )
        return "", HTTPStatus.OK
