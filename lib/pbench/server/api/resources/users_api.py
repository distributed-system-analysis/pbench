from http import HTTPStatus

from flask import jsonify, make_response
from flask.wrappers import Response
from flask_restful import abort, Resource

import pbench.server.auth.auth as Auth
from pbench.server.database.models.server_config import ServerConfig


class UserAPI(Resource):
    """
    Abstracted pbench API to get user data
    """

    @Auth.token_auth.login_required()
    def get(self, target_username: str) -> Response:
        """
        Get request for getting user data.

        Required headers include
            Authorization:  Bearer Pbench_auth_token (user received upon login)

        Note: If the Admin user is perorming a GET on a different target
        username, then the cached target user entry data wil be returned.

        Args:
            target_username: target username string to perform get request on

        Returns: JSON Payload
            Success: 200,
                    response_object = {
                        "username": <username>,
                        "email": <email>
                        "first_name": <firstName>,
                        "last_name": <lastName>,
                        "created": <registered_on>,
                    }
            Failure: <status_Code>,
                    response_object = {
                        "message": "failure message"
                    }
        """
        disabled = ServerConfig.get_disabled(readonly=True)
        if disabled:
            abort(HTTPStatus.SERVICE_UNAVAILABLE, **disabled)

        auth_token = Auth.get_auth_token()
        current_user = Auth.token_auth.current_user()
        response_object = {}

        if current_user.username == target_username:
            token_payload = Auth.oidc_client.token_introspect(auth_token)
            response_object = {
                "username": token_payload.get("preferred_username"),
                "first_name": token_payload.get("given_name"),
                "last_name": token_payload.get("family_name"),
                "email": token_payload.get("email"),
            }
        else:
            # If the decoded token does not contain the targeted username,
            # return FORBIDDEN
            abort(HTTPStatus.FORBIDDEN, message="Forbidden to perform the GET request")

        return make_response(jsonify(response_object), HTTPStatus.OK)
