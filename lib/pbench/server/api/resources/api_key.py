from http import HTTPStatus

from flask import jsonify
from flask.wrappers import Request, Response

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
from pbench.server.database.models.api_keys import APIKey, APIKeyError
from pbench.server.database.models.audit import (
    Audit,
    AuditStatus,
    AuditType,
    OperationCode,
)


class APIKeyManage(ApiBase):
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

    def _post(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Post request for generating a new persistent API key.

        Required headers include

            Content-Type:   application/json
            Accept:         application/json

        Returns:
            Success: 201 with api_key

        Raises:
            APIAbort, reporting "UNAUTHORIZED"
            APIInternalError, reporting the failure message
        """
        user = Auth.token_auth.current_user()

        if not user:
            raise APIAbort(
                HTTPStatus.UNAUTHORIZED,
                "User provided access_token is invalid or expired",
            )
        try:
            new_key = APIKey.generate_api_key(user)
        except APIKeyError as e:
            raise APIInternalError(e.message) from e
        except Exception as e:
            raise APIInternalError("Unexpected backend error") from e

        try:
            key = APIKey(api_key=new_key, user=user)
            key.add()
        except APIKeyError as e:
            raise APIInternalError(e.message) from e
        except Exception as e:
            raise APIInternalError(e) from e

        Audit.create(
            operation=OperationCode.CREATE,
            name="api_key",
            user_id=user.id,
            object_type=AuditType.API_KEY,
            user_name=user.username,
            status=AuditStatus.SUCCESS,
        )

        response = jsonify({"api_key": new_key})
        response.status = HTTPStatus.CREATED
        return response
