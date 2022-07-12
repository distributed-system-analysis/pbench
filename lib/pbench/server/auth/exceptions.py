from http import HTTPStatus


class KeycloakError(Exception):
    def __init__(self, http_status: int, message: str = None):
        self.http_status = http_status
        self.message = message if message else HTTPStatus(http_status).phrase

    def __repr__(self) -> str:
        return f"Keycloak error {self.http_status} : {str(self)}"

    def __str__(self) -> str:
        return self.message


class KeycloakConfigError(KeycloakError):
    pass


class KeycloakConnectionError(KeycloakError):
    pass
