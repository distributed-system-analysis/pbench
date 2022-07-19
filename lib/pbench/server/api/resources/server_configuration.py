from http import HTTPStatus
from logging import Logger

from flask.json import jsonify
from flask.wrappers import Request, Response

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    APIAbort,
    API_OPERATION,
    ApiBase,
    ApiParams,
    ApiSchema,
    MissingParameters,
    ParamType,
    Parameter,
    Schema,
)
from pbench.server.database.models.server_config import (
    ServerConfig,
    ServerConfigBadValue,
    ServerConfigError,
)


class ServerConfiguration(ApiBase):
    """
    API class to retrieve and mutate Dataset metadata.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.PUT,
                API_OPERATION.UPDATE,
                uri_schema=Schema(
                    Parameter("key", ParamType.KEYWORD, keywords=ServerConfig.KEYS)
                ),
                # TODO: We aspire to be flexible about how a config option is
                # specified on a PUT. While the "config" parameter is specifically
                # intended to support a full JSON body that sets or updates all
                # options at once, for individual options using the "value"
                # query parameter is probably easier... but the "value" body
                # parameter also allows specifying the value in a body.
                #
                #   PUT /server/configuration/dataset-lifetime?value=2y
                #   PUT /server/configuration/dataset-lifetime
                #       {"value": "2y"}
                #   PUT /server/configuration/dataset-lifetime ???
                #       {"config": {"dataset-lifetime": "2y"}}
                #
                # Some options may not make sense: need to think about this.
                query_schema=Schema(Parameter("value", ParamType.STRING)),
                body_schema=Schema(
                    Parameter("config", ParamType.JSON, keywords=ServerConfig.KEYS),
                    Parameter("value", ParamType.JSON),
                ),
                authorization=API_AUTHORIZATION.ADMIN,
            ),
            ApiSchema(
                API_METHOD.GET,
                API_OPERATION.READ,
                uri_schema=Schema(
                    Parameter("key", ParamType.KEYWORD, keywords=ServerConfig.KEYS)
                ),
                authorization=API_AUTHORIZATION.NONE,
            ),
            always_enabled=True,
        )

    def _get(self, params: ApiParams, request: Request) -> Response:
        """
        Get the values of server configuration parameters.

        Args:
            params: API parameters
            request: The original Request object containing query parameters

        GET /api/v1/server/configuration?key=config1&key=config2
        """

        key = params.uri.get("key")
        try:
            if key:
                s = ServerConfig.get(key)
                return jsonify({key: s.value if s else None})
            else:
                return jsonify(ServerConfig.get_all())
        except ServerConfigError as e:
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))

    def _put(self, params: ApiParams, _) -> Response:
        """
        Set or modify the values of server configuration keys.

        PUT /api/v1/server/configuration
        {
            "config": {
                "dataset-lifetime": 10,
                "server-state": "running"
            }
        }

        PUT /api/v1/server/configuration/dataset-lifetime?value=10

        PUT /api/v1/server/configuration/dataset-lifetime
        {
            "value": "10"
        }
        """

        try:
            key = params.uri["key"]
            try:
                value = params.query["value"]
            except KeyError:
                try:
                    value = params.body["value"]
                except KeyError:
                    raise APIAbort(
                        HTTPStatus.BAD_REQUEST,
                        "Incorrect value specification for key {key!r}",
                    )
            try:
                ServerConfig.set(key=key, value=value)
                return jsonify({key: value})
            except ServerConfigBadValue as e:
                raise APIAbort(HTTPStatus.BAD_REQUEST, str(e))
            except ServerConfigError as e:
                raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))
        except KeyError:
            pass

        try:
            config = params.body["config"]
        except KeyError:
            raise MissingParameters(["config"])

        failures = []
        for k, v in config.items():
            try:
                ServerConfig.set(key=k, value=v)
            except ServerConfigError as e:
                self.logger.warning("Unable to update key {} = {!r}: {}", k, v, str(e))
                failures.append(k)
        if failures:
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR)
        return jsonify(ServerConfig.get_all())
