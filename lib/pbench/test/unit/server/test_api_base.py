from typing import Optional

from flask import Flask
from flask.wrappers import Request, Response
from flask_restful import Api

from pbench.server import JSONOBJECT, OperationCode
from pbench.server.api.resources import (
    ApiBase,
    ApiContext,
    ApiMethod,
    ApiParams,
    ApiSchema,
)
from pbench.server.auth.auth import Auth
from pbench.server.database.models.server_config import ServerConfig


class OnlyGet(ApiBase):
    def __init__(self, server_config, logger):
        super().__init__(
            server_config, logger, ApiSchema(ApiMethod.GET, OperationCode.READ)
        )

    def _get(self, args: ApiParams, request: Request, context: ApiContext) -> str:
        return "OK - Only GET"


class Always(ApiBase):
    def __init__(self, server_config, logger):
        super().__init__(
            server_config,
            logger,
            ApiSchema(ApiMethod.GET, OperationCode.READ),
            always_enabled=True,
        )

    def _get(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        return "OK - Always GET"


class All(ApiBase):
    def __init__(self, server_config, logger):
        super().__init__(
            server_config,
            logger,
            ApiSchema(ApiMethod.GET, OperationCode.READ),
            ApiSchema(ApiMethod.HEAD, OperationCode.READ),
            ApiSchema(ApiMethod.POST, OperationCode.CREATE),
            ApiSchema(ApiMethod.PUT, OperationCode.UPDATE),
            ApiSchema(ApiMethod.DELETE, OperationCode.DELETE),
        )

    def _get(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        return "OK - All GET"

    def _head(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        return "OK - All HEAD"

    def _post(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        return "OK - All POST"

    def _put(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        return "OK - All PUT"

    def _delete(
        self, args: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        return "OK - All DELETE"


class OptionsMethod(ApiBase):
    def __init__(self, server_config, logger):
        super().__init__(
            server_config,
            logger,
            ApiSchema(99, OperationCode.READ),
        )

    def options(self, **kwargs) -> Response:
        return self._dispatch(99, kwargs)


class TestApiBase:
    """Verify internal methods of the API base class."""

    def test_method_validation(
        self, server_config, make_logger, monkeypatch, set_oidc_well_known_endpoints
    ):
        # Create the temporary flask application.
        app = Flask("test-api-server")
        app.debug = True
        app.testing = True
        app.logger = make_logger

        token_auth = Auth()
        token_auth.set_logger(app.logger)
        Auth.set_oidc_client(server_config=server_config)

        # Mimic our normal use of ApiBase with our sub-classed instances.
        api = Api(app)
        api.add_resource(
            OnlyGet,
            "/api/v1/onlyget",
            endpoint="onlyget",
            resource_class_args=(server_config, app.logger),
        )
        api.add_resource(
            Always,
            "/api/v1/always",
            endpoint="always",
            resource_class_args=(server_config, app.logger),
        )
        api.add_resource(
            All,
            "/api/v1/all",
            endpoint="all",
            resource_class_args=(server_config, app.logger),
        )
        api.add_resource(
            OptionsMethod,
            "/api/v1/other",
            endpoint="other",
            resource_class_args=(server_config, app.logger),
        )

        # Flask-provided test client
        client = app.test_client()

        def mock_get_disabled(readonly: bool = False) -> Optional[JSONOBJECT]:
            return None

        monkeypatch.setattr(ServerConfig, "get_disabled", mock_get_disabled)

        # Verify all allowed APIs
        response = client.get("/api/v1/onlyget")
        assert response.status_code == 200

        response = client.get("/api/v1/always")
        assert response.status_code == 200

        response = client.get("/api/v1/all")
        assert response.status_code == 200
        response = client.head("/api/v1/all")
        assert response.status_code == 200
        response = client.post("/api/v1/all")
        assert response.status_code == 200
        response = client.put("/api/v1/all")
        assert response.status_code == 200
        response = client.delete("/api/v1/all")
        assert response.status_code == 200

        # Verify method not allowed for method general method
        response = client.options("/api/v1/other")
        assert response.status_code == 405

        response = client.put("/api/v1/onlyget")
        assert response.status_code == 405
