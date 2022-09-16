from logging import Logger

from pbench.server import JSON, PbenchServerConfig
from pbench.server.api.resources import (
    API_METHOD,
    API_OPERATION,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import CONTEXT, ElasticBase


class Elasticsearch(ElasticBase):
    """Elasticsearch API for post request via server."""

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        """
        __init__ Configure the Elasticsearch passthrough class

        NOTE: This API is obsolescent. We've talked about retaining it as a
        potentially "privileged" mechanism to gain direct access to the
        Elasticsearch backend, but this isn't defined. We should likely
        delete it, or at least remove it from the API routing, until then;
        for now I've given it the minimum coat of paint to build under the
        new schema infrastructure rather than tackling those issues at the
        same time.

        Args:
            config: Pbench configuration object
            logger: logger object
        """
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.POST,
                API_OPERATION.UPDATE,
                body_schema=Schema(
                    Parameter("indices", ParamType.STRING, required=True),
                    Parameter("payload", ParamType.JSON),
                    Parameter("params", ParamType.JSON),
                ),
            ),
        )

    def assemble(self, params: ApiParams, context: CONTEXT) -> JSON:
        return {
            "path": params.body["indices"],
            "kwargs": {
                "json": params.body.get("payload"),
                "params": params.body.get("params"),
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        return es_json
