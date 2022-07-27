from http import HTTPStatus
from logging import Logger

from flask.json import jsonify
from flask.wrappers import Request, Response

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    API_AUTHORIZATION,
    API_METHOD,
    API_OPERATION,
    APIAbort,
    ApiBase,
    ApiParams,
    ApiSchema,
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
    API class to retrieve and mutate server configuration settings.
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
                # We aspire to be flexible about how a config option is
                # specified on a PUT. The value of a single config option can
                # be set using the "value" query parameter or the "value" JSON
                # body parameter. You can also specify one config option or
                # multiple config options by omitting the key name from the URI
                # and specifying the names and values in a JSON request body:
                #
                #   PUT /server/configuration/dataset-lifetime?value=2y
                #   PUT /server/configuration/dataset-lifetime
                #       {"value": "2y"}
                #   PUT /server/configuration
                #       {"dataset-lifetime": "2y"}
                query_schema=Schema(Parameter("value", ParamType.STRING)),
                body_schema=Schema(
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

        GET /api/v1/server/configuration/{key}
            return the value of a single configuration parameter

        or

        GET /api/v1/server/configuration
            return all configuration parameters
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
            "dataset-lifetime": 10,
            "server-state": "running"
        }

        PUT /api/v1/server/configuration/dataset-lifetime?value=10

        PUT /api/v1/server/configuration/dataset-lifetime
        {
            "value": "10"
        }
        """

        # First, we check for the ways to set an individual config setting by
        # naming the config key on the URI and specifying a value either with
        # the "value" either as a query parameter or in the JSON request body.
        #
        # We'll complain about JSON request body parameters that are "shadowed"
        # by the URI or query parameter and might represent client confusion.
        keydup = set()
        key = params.uri.get("key")
        if key:
            # If we have a key in the URL, the we need a "value" for it, which
            # we can take either from a query parameter or from the JSON
            # request payload.
            if params.body and list(params.body.keys()) != ["value"]:
                keydup.update(params.body.keys())
            value = params.query.get("value")
            if value:
                if params.body:
                    keydup.update(params.body.keys())
            else:
                value = params.body.get("value")
                if not value:
                    raise APIAbort(
                        HTTPStatus.BAD_REQUEST,
                        f"No value found for key system configuration key {key!r}",
                    )

            if len(keydup) > 0:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"Redundant parameters specified in the JSON request body: {sorted(keydup)!r}",
                )

            try:
                ServerConfig.set(key=key, value=value)
                return jsonify({key: value})
            except ServerConfigBadValue as e:
                raise APIAbort(HTTPStatus.BAD_REQUEST, str(e))
            except ServerConfigError as e:
                raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))

        else:
            # If we get here, we didn't get "key" from the URI, so we're expecting
            # a JSON request body with key/value pairs, potentially for multiple
            # config options.
            badkeys = []
            for k, v in params.body.items():
                if k not in ServerConfig.KEYS:
                    badkeys.append(k)

            if badkeys:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"Unrecognized configuration parameters {sorted(badkeys)!r} specified: valid parameters are {sorted(ServerConfig.KEYS)!r}",
                )

            failures = []
            response = {}
            fail_status = HTTPStatus.BAD_REQUEST
            for k, v in params.body.items():
                try:
                    c = ServerConfig.set(key=k, value=v)
                    response[c.key] = c.value
                except ServerConfigBadValue as e:
                    failures.append(str(e))
                except ServerConfigError as e:
                    fail_status = HTTPStatus.INTERNAL_SERVER_ERROR
                    self.logger.warning(str(e))
                    failures.append(str(e))
            if failures:
                raise APIAbort(fail_status, message=", ".join(failures))
            return jsonify(response)
