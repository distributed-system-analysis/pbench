from http import HTTPStatus

from pbench.test.unit.server.headertypes import HeaderTypes


class Testuser:
    def test_get_user(self, client, server_config, build_auth_header):
        header_param = build_auth_header["header_param"]
        response = client.get(
            f"{server_config.rest_uri}/user/drb",
            headers=build_auth_header["header"],
        )
        if header_param is HeaderTypes.VALID:
            assert response.status_code == HTTPStatus.OK
            assert response.json == {
                "username": "drb",
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "dummy@example.com",
            }
        elif header_param is HeaderTypes.VALID_ADMIN:
            # If the username from the decoded token does not match the targeted
            # username, we expect the return status to be FORBIDDEN.
            assert response.status_code == HTTPStatus.FORBIDDEN
            assert response.json["message"] == "Forbidden to perform the GET request"
        else:
            assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_get_non_existent_user(self, client, server_config, build_auth_header):
        header_param = build_auth_header["header_param"]
        response = client.get(
            f"{server_config.rest_uri}/user/nonexistent",
            headers=build_auth_header["header"],
        )
        if HeaderTypes.is_valid(header_param):
            assert response.status_code == HTTPStatus.FORBIDDEN
        else:
            assert response.status_code == HTTPStatus.UNAUTHORIZED
            assert response.json is None
