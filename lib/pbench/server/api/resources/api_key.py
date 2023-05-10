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
    Parameter,
    ParamType,
    Schema,
)
import pbench.server.auth.auth as Auth
from pbench.server.database.models.api_keys import APIKey, DuplicateApiKey
from pbench.server.database.models.audit import AuditType, OperationCode


class APIKeyManage(ApiBase):
    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.POST,
                OperationCode.CREATE,
                query_schema=Schema(
                    Parameter("label", ParamType.STRING, required=False),
                ),
                audit_type=AuditType.API_KEY,
                audit_name="apikey",
                authorization=ApiAuthorizationType.NONE,
            ),
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                uri_schema=Schema(
                    Parameter("key", ParamType.STRING, required=False),
                ),
                authorization=ApiAuthorizationType.NONE,
            ),
            ApiSchema(
                ApiMethod.DELETE,
                OperationCode.DELETE,
                uri_schema=Schema(
                    Parameter("key", ParamType.STRING, required=True),
                ),
                audit_type=AuditType.API_KEY,
                audit_name="apikey",
                authorization=ApiAuthorizationType.NONE,
            ),
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """Get a list of API keys associated with the user.

        GET /api/v1/key

        Returns:
            Success: 200 with response containing the requested api_key
                or list of api_key

        Raises:
            APIAbort, reporting "UNAUTHORIZED" or "NOT_FOUND"
        """
        user = Auth.token_auth.current_user()

        if not user:
            raise APIAbort(
                HTTPStatus.UNAUTHORIZED,
                "User provided access_token is invalid or expired",
            )

        key_id = params.uri.get("key")
        if not key_id:
            keys = APIKey.query(user=user)
            return [key.as_json() for key in keys]

        else:
            key = APIKey.query(id=key_id, user=user)
            if not key:
                raise APIAbort(HTTPStatus.NOT_FOUND, "Requested key not found")
            return key[0].as_json()

    def _post(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Post request for generating a new persistent API key.

        POST /api/v1/key?label=label

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
        label = params.query.get("label")

        if context["raw_params"].uri:
            raise APIAbort(HTTPStatus.BAD_REQUEST, "Key cannot be specified by the user")


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
            key = APIKey(key=new_key, user=user, label=label)
            key.add()
            status = HTTPStatus.CREATED
        except DuplicateApiKey:
            status = HTTPStatus.OK
        except Exception as e:
            raise APIInternalError(str(e)) from e
        context["auditing"]["attributes"] = key.as_json()
        response = jsonify(key.as_json())
        response.status_code = status
        return response

    def _delete(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """Delete the requested key.

        DELETE /api/v1/key/{key}

        Returns:
            Success: 200

        Raises:
            APIAbort, reporting "UNAUTHORIZED" or "NOT_FOUND"
            APIInternalError, reporting the failure message
        """
        key_id = params.uri["key"]
        user = Auth.token_auth.current_user()

        if not user:
            raise APIAbort(
                HTTPStatus.UNAUTHORIZED,
                "User provided access_token is invalid or expired",
            )
        term = {"id": key_id}
        if not user.is_admin():
            term["user"] = user
        keys = APIKey.query(**term)
        if not keys:
            raise APIAbort(HTTPStatus.NOT_FOUND, "Requested key not found")
        key = keys[0]
        try:
            context["auditing"]["attributes"] = key.as_json()
            key.delete()
            return "deleted", HTTPStatus.OK
        except Exception as e:
            raise APIInternalError(str(e)) from e
