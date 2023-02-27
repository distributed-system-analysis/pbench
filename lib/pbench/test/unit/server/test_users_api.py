from http import HTTPStatus

from pbench.test.unit.server import DRB_USER_ID
from pbench.test.unit.server.headertypes import HeaderTypes


class Testuser:
    def test_get_user(self, client, server_config, build_auth_header):
        header_param = build_auth_header["header_param"]
        expected_status = HTTPStatus.OK
        if not HeaderTypes.is_valid(header_param):
            expected_status = HTTPStatus.UNAUTHORIZED

        response = client.get(
            f"{server_config.rest_uri}/user/drb",
            headers=build_auth_header["header"],
        )
        assert response.status_code == expected_status
        if header_param is HeaderTypes.VALID_ADMIN:
            assert response.json == {
                "username": "drb",
                "id": DRB_USER_ID,
                "roles": [],
            }
        elif header_param is HeaderTypes.VALID:
            assert response.json == {
                "username": "drb",
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "dummy@example.com",
            }
        else:
            assert response.json is None

    def test_get_non_existent_user(self, client, server_config, build_auth_header):
        header_param = build_auth_header["header_param"]
        response = client.get(
            f"{server_config.rest_uri}/user/nonexistent",
            headers=build_auth_header["header"],
        )
        if header_param is HeaderTypes.VALID_ADMIN:
            assert response.status_code == HTTPStatus.NOT_FOUND
        elif header_param is HeaderTypes.VALID:
            assert response.status_code == HTTPStatus.FORBIDDEN
        else:
            assert response.status_code == HTTPStatus.UNAUTHORIZED
            assert response.json is None
