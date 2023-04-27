from http import HTTPStatus

from flask import jsonify
from flask.wrappers import Request, Response

from pbench.server import JSONOBJECT, PbenchServerConfig
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
                    Parameter("name", ParamType.STRING, required=True),
                ),
                audit_type=AuditType.API_KEY,
                audit_name="apikey",
                authorization=ApiAuthorizationType.NONE,
            ),
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
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
            Success: 200 with response containing the list of api_key

        Raises:
            APIAbort, reporting "UNAUTHORIZED"
        """
        user = Auth.token_auth.current_user()

        if not user:
            raise APIAbort(
                HTTPStatus.UNAUTHORIZED,
                "User provided access_token is invalid or expired",
            )

        key = APIKey.query(user=user)
        key_dict: JSONOBJECT = {}
        if key:
            for i in key:key_dict[i.name] = i.api_key

        response = {"api_key": key_dict}
        return response

    def _post(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Post request for generating a new persistent API key.

        POST /api/v1/key?name=name

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
        name = params.query.get("name")

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
            key = APIKey(api_key=new_key, user=user, name=name)
            key.add()
            status = HTTPStatus.CREATED
        except DuplicateApiKey:
            status = HTTPStatus.OK
        except Exception as e:
            raise APIInternalError(str(e)) from e

        context["auditing"]["attributes"] = {"key": new_key, "name": name}
        response = jsonify({"api_key": new_key})
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
            APIAbort, reporting "UNAUTHORIZED" and "FORBIDDEN"
            APIInternalError, reporting the failure message
        """
        api_key = params.uri["key"]
        user = Auth.token_auth.current_user()

        if not user:
            raise APIAbort(
                HTTPStatus.UNAUTHORIZED,
                "User provided access_token is invalid or expired",
            )
        key = APIKey.query(api_key=api_key)
        if not key:
            raise APIAbort(HTTPStatus.NOT_FOUND, "Requested key not found")
        if key.user == user:
            try:
                APIKey.delete(api_key)
                return "", HTTPStatus.OK
            except Exception as e:
                raise APIInternalError(str(e)) from e
        else:
            raise APIAbort(
                HTTPStatus.FORBIDDEN,
                "User does not have rights to delete the specified key",
            )
