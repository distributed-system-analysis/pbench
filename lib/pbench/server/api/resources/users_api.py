from http import HTTPStatus

from flask import current_app, jsonify, make_response
from flask.wrappers import Request, Response

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorization,
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
from pbench.server.database.models.users import (
    User,
    UserProfileBadKey,
    UserProfileBadStructure,
)


class UserAPI(ApiBase):
    """
    Abstracted pbench API to get user data
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.PUT,
                OperationCode.UPDATE,
                uri_schema=Schema(
                    Parameter("target_username", ParamType.USER, required=True)
                ),
                body_schema=Schema(
                    Parameter(
                        "profile",
                        ParamType.JSON,
                        required=True,
                        key_path=True,
                    )
                ),
                authorization=ApiAuthorizationType.NONE,
            ),
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                uri_schema=Schema(
                    Parameter("target_username", ParamType.USER, required=True)
                ),
                authorization=ApiAuthorizationType.NONE,
            ),
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """Get request for acessing user data.
        This requires a Bearer auth token in the header field

        Note: User data is imported in the user table by decoding the
              OIDC access_token.

        Required headers include
            Authorization:  Bearer auth_token
        Args:
            params: API parameters
            request: The original Request object containing query parameters
            context: API context dictionary

        Returns:
            Flask Resposne payload
            Success: 200,
                    response_object = {
                        "username": <username>,
                        "profile": <profile_json>
                    }
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        """
        target_user_id = params.uri["target_username"]
        self._check_authorization(
            ApiAuthorization(
                ApiAuthorizationType.USER_ACCESS,
                OperationCode.READ,
                target_user_id,
            )
        )
        target_user = User.query(id=int(target_user_id))
        response_object = target_user.get_json()
        return make_response(jsonify(response_object), HTTPStatus.OK)

    def _put(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """PUT request for updating user profile data.
        This requires a Bearer token in the header field

        The request accept any of the following json format:
            1. {"user.key1": "value", "user.key2.key3": "Value"}
            2. {"user": {"key": {"key1": "value"}}}
            3. {"user": {"key.key1": "value"}}

        Note: username is not updatatble.

        Example Json:
        {
            profile: {"user.first_name": "new_name"},
            ...
        }

        Required headers include

            Content-Type:   application/json
            Authorization:  Bearer auth_token

        Args:
            params: API parameters
            request: The original Request object containing query parameters
            context: API context dictionary

        Returns:
            Updated profile JSON Payload
            Success: 200, and response_object with updated fields
                    response_object = {
                        "username": <username>,
                        "profile": <new_profile>
                        ...
                    }
            Failure: <status_Code>
                    response_object = {
                        "message": "failure message"
                    }
        """
        target_user_id = params.uri["target_username"]
        self._check_authorization(
            ApiAuthorization(
                ApiAuthorizationType.USER_ACCESS,
                OperationCode.READ,
                target_user_id,
            )
        )
        target_user = User.query(id=int(target_user_id))
        user_payload = params.body["profile"]

        try:
            valid_dict = target_user.form_valid_dict(**user_payload)
            target_user.update(valid_dict)
        except UserProfileBadKey as e:
            current_app.logger.debug(
                "User tried updating non updatable profile key, {}", user_payload
            )
            raise APIAbort(HTTPStatus.BAD_REQUEST, message=str(e))
        except UserProfileBadStructure as e:
            current_app.logger.debug("Bad user prfile structure, {}", user_payload)
            raise APIAbort(HTTPStatus.BAD_REQUEST, message=str(e))
        except Exception:
            current_app.logger.exception(
                "Exception occurred during updating user object"
            )
            raise APIInternalError(
                HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR"
            )

        response_object = target_user.get_json()
        return make_response(jsonify(response_object), HTTPStatus.OK)
