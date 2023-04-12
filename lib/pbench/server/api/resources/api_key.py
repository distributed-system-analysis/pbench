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
from pbench.server.database.models.api_keys import APIKey
from pbench.server.database.models.audit import AuditType, OperationCode


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
        except Exception as e:
            raise APIInternalError(str(e)) from e

        try:
            key = APIKey(api_key=new_key, user=user)
            key.add()
        except APIKey.DuplicateValue:
            pass
        except Exception as e:
            raise APIInternalError(str(e)) from e

        context["auditing"]["attributes"] = {"key": new_key}
        response = jsonify({"api_key": new_key})
        response.status = HTTPStatus.CREATED
        return response
