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

        GET /api/v1/server/configuration/{key}
            return the value of a single configuration parameter

        or

        GET /api/v1/server/configuration
            return all configuration parameters

        Args:
            params: API parameters
            request: The original Request object containing query parameters

        Returns:
            HTTP Response object
        """

        key = params.uri.get("key")
        try:
            if key:
                s = ServerConfig.get(key)
                return jsonify({key: s.value if s else None})
            else:
                return jsonify(ServerConfig.get_all())
        except ServerConfigError as e:
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR, str(e)) from e

    def _put_key(self, params: ApiParams) -> Response:
        """
        Implement the PUT operation when a system configuration setting key is
        specified on the URI as /system/configuration/{key}.

        A single system config setting is set by naming the config key in the
        URI and specifying a value using either the "value" query parameter or
        a "value" key in a JSON request body.

        We'll complain about JSON request body parameters that are "shadowed"
        by the "value" query parameter and might represent client confusion.
        We won't complain about unnecessary JSON request body keys if we find
        the "value" in the request body as those would normally have been
        ignored by schema validation.

        Args:
            params: API parameters
            request: The original Request object containing query parameters

        Returns:
            HTTP Response object
        """

        try:
            key = params.uri["key"]
        except KeyError:
            # This "isn't possible" given the Flask mapping rules, but try
            # to report it gracefully instead of letting the KeyError fly.
            raise APIAbort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Found URI parameters {sorted(params.uri)} not including 'key'",
            )

        # If we have a key in the URL, then we need a "value" for it, which
        # we can take either from a query parameter or from the JSON
        # request payload.
        value = params.query.get("value")
        if value:
            # If we got the value from the query parameter, complain about
            # any JSON request body keys
            if params.body:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    "Redundant parameters specified in the JSON request body: "
                    f"{sorted(params.body.keys())!r}",
                )
        else:
            value = params.body.get("value")
            if not value:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"No value found for key system configuration key {key!r}",
                )

        try:
            ServerConfig.set(key=key, value=value)
        except ServerConfigBadValue as e:
            raise APIAbort(HTTPStatus.BAD_REQUEST, str(e)) from e
        except ServerConfigError as e:
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR, str(e)) from e
        return jsonify({key: value})

    def _put_body(self, params: ApiParams) -> Response:
        """
        Allow setting the value of multiple system configuration settings with
        a single PUT by specifying a JSON request body with key/value pairs.

        Args:
            params: API parameters
            request: The original Request object containing query parameters

        Returns:
            HTTP Response object
        """
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

        Args:
            params: API parameters
            request: The original Request object containing query parameters

        Returns:
            HTTP Response object
        """

        if params.uri:
            return self._put_key(params)
        else:
            return self._put_body(params)
