from http import HTTPStatus

from flask import current_app
from flask.json import jsonify
from flask.wrappers import Request, Response

from pbench.server import OperationCode, PbenchServerConfig
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
from pbench.server.database.models.audit import AuditType
from pbench.server.database.models.server_settings import (
    ServerSetting,
    ServerSettingBadValue,
    ServerSettingError,
)


class ServerSettings(ApiBase):
    """
    API class to retrieve and mutate server settings.
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.PUT,
                OperationCode.UPDATE,
                uri_schema=Schema(
                    Parameter("key", ParamType.KEYWORD, keywords=ServerSetting.KEYS)
                ),
                # We aspire to be flexible about how a setting is specified on a
                # PUT. The value of a single setting can be set using the
                # "value" query parameter or the "value" JSON body parameter.
                # You can also specify one setting or multiple settings by
                # omitting the key name from the URI and specifying the names
                # and values in a JSON request body:
                #
                #   PUT /server/settings/dataset-lifetime?value=2y
                #   PUT /server/settings/dataset-lifetime
                #       {"value": "2y"}
                #   PUT /server/settings
                #       {"dataset-lifetime": "2y"}
                query_schema=Schema(Parameter("value", ParamType.STRING)),
                body_schema=Schema(
                    Parameter("value", ParamType.JSON),
                ),
                audit_type=AuditType.CONFIG,
                audit_name="config",
                authorization=ApiAuthorizationType.ADMIN,
            ),
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                uri_schema=Schema(
                    Parameter("key", ParamType.KEYWORD, keywords=ServerSetting.KEYS)
                ),
                authorization=ApiAuthorizationType.NONE,
            ),
            always_enabled=True,
        )

    def _get(self, params: ApiParams, req: Request, context: ApiContext) -> Response:
        """
        Get the values of server settings.

        GET /api/v1/server/settings/{key}
            return the value of a single server setting

        or

        GET /api/v1/server/settings
            return all server settings

        Args:
            params: API parameters
            req: The original Request object containing query parameters
            context: API context dictionary

        Returns:
            HTTP Response object
        """

        key = params.uri.get("key")
        try:
            if key:
                s = ServerSetting.get(key)
                return jsonify({key: s.value if s else None})
            else:
                return jsonify(ServerSetting.get_all())
        except ServerSettingError as e:
            raise APIInternalError(f"Error reading server setting {key}") from e

    def _put_key(self, params: ApiParams, context: ApiContext) -> Response:
        """
        Implement the PUT operation when a server setting key is specified on
        the URI as /server/settings/{key}.

        A single server setting is set by naming the key in the URI and
        specifying a value using either the "value" query parameter or a "value"
        key in a JSON request body.

        We'll complain about JSON request body parameters that are "shadowed"
        by the "value" query parameter and might represent client confusion.
        We won't complain about unnecessary JSON request body keys if we find
        the "value" in the request body as those would normally have been
        ignored by schema validation.

        Args:
            params: API parameters
            context: CONTEXT dictionary

        Returns:
            HTTP Response object
        """

        try:
            key = params.uri["key"]
        except KeyError:
            # This "isn't possible" given the Flask mapping rules, but try
            # to report it gracefully instead of letting the KeyError fly.
            raise APIAbort(HTTPStatus.BAD_REQUEST, message="Missing parameter 'key'")

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
                    f"No value found for server settings key {key!r}",
                )

        context["auditing"]["attributes"] = {"updated": {key: value}}

        try:
            ServerSetting.set(key=key, value=value)
        except ServerSettingBadValue as e:
            raise APIAbort(HTTPStatus.BAD_REQUEST, str(e)) from e
        except ServerSettingError as e:
            raise APIInternalError(f"Error setting server setting {key}") from e
        return jsonify({key: value})

    def _put_body(self, params: ApiParams, context: ApiContext) -> Response:
        """
        Allow setting the value of multiple server settings with a single PUT by
        specifying a JSON request body with key/value pairs.

        Args:
            params: API parameters
            context: CONTEXT dictionary

        Returns:
            HTTP Response object
        """
        badkeys = []
        for k, v in params.body.items():
            if k not in ServerSetting.KEYS:
                badkeys.append(k)

        if badkeys:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST,
                f"Unrecognized server settings {sorted(badkeys)!r} specified: valid settings are {sorted(ServerSetting.KEYS)!r}",
            )

        context["auditing"]["attributes"] = {"updated": params.body}

        failures = []
        response = {}
        for k, v in params.body.items():
            try:
                c = ServerSetting.set(key=k, value=v)
                response[c.key] = c.value
            except ServerSettingBadValue as e:
                failures.append(str(e))
            except Exception as e:
                current_app.logger.warning("{}", e)
                raise APIInternalError(f"Error setting server setting {k}")
        if failures:
            raise APIAbort(HTTPStatus.BAD_REQUEST, message=", ".join(failures))
        return jsonify(response)

    def _put(self, params: ApiParams, req: Request, context: ApiContext) -> Response:
        """
        Set or modify the values of server setting keys.

        PUT /api/v1/server/settings
        {
            "dataset-lifetime": 10,
            "server-state": "running"
        }

        PUT /api/v1/server/settings/dataset-lifetime?value=10

        PUT /api/v1/server/settings/dataset-lifetime
        {
            "value": "10"
        }

        Args:
            params: API parameters
            req: The original Request object containing query parameters
            context: API context dictionary

        Returns:
            HTTP Response object
        """

        if params.uri:
            return self._put_key(params, context)
        else:
            return self._put_body(params, context)
