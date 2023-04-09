from http import HTTPStatus

from flask import jsonify, make_response
from flask.wrappers import Request, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiBase,
    ApiContext,
    APIInternalError,
    ApiMethod,
    ApiParams,
    ApiSchema,
)
import pbench.server.auth.auth as Auth
from pbench.server.database.models.api_key import APIKeyError, APIKeys
from pbench.server.database.models.audit import (
    Audit,
    AuditStatus,
    AuditType,
    OperationCode,
)


class APIKey(ApiBase):
    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.POST,
                OperationCode.CREATE,
                audit_type=AuditType.API_KEY,
                audit_name="apikey",
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

        Returns:
            Success: 201 with api_key and user

        Raises:
            APIAbort, reporting "UNAUTHORIZED"
            APIInternalError, reporting the failure message
        """
        user = Auth.token_auth.current_user()

        if not user:
            raise APIAbort(
                HTTPStatus.UNAUTHORIZED,
                "User provided access_token is invalid or expired token",
            )
        try:
            new_key = APIKeys.generate_api_key(Auth, user=user)
        except APIKeyError as e:
            raise APIInternalError(e.message)
        except Exception as e:
            raise APIInternalError("Unexpected backend error") from e

        try:
            key = APIKeys(
                api_key=new_key,
                user=user,
            )
            key.add()
        except IntegrityError:
            raise APIInternalError("Duplicate api_key exists in the DB")
        except SQLAlchemyError:
            raise APIInternalError(
                "SQLAlchemy Exception while adding an api_key in the DB"
            )
        except APIKeyError as e:
            raise APIInternalError(e.message)
        except Exception:
            raise APIInternalError("Error while adding api_key to the DB")

        Audit.create(
            operation=OperationCode.CREATE,
            name="api_key",
            user_id=user.id,
            object_type=AuditType.API_KEY,
            user_name=user.username,
            status=AuditStatus.SUCCESS,
        )

        response_object = {
            "api_key": new_key,
            "username": user.username,
        }
        return make_response(jsonify(response_object), HTTPStatus.CREATED)
