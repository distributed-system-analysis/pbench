from logging import Logger

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import JSON, Schema, Parameter, ParamType
from pbench.server.api.resources.query_apis import CONTEXT, ElasticBase


class Elasticsearch(ElasticBase):
    """Elasticsearch API for post request via server."""

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        """
        __init__ Configure the Elasticsearch passthrough class

        NOTE: there are three "expected" JSON input parameters, but only two of
        these are required and therefore appear in the schema.

        TODO: the schema could be extended to include both the type and a
        "required" flag; is that worthwhile? This would allow automatic type
        check/conversion of optional parameters, which would be cleaner.

        Args:
            config: Pbench configuration object
            logger: logger object
        """
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("indices", ParamType.STRING, required=True),
                Parameter("payload", ParamType.JSON),
                Parameter("params", ParamType.JSON),
            ),
        )

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        return {
            "path": json_data["indices"],
            "kwargs": {
                "json": json_data.get("payload"),
                "params": json_data.get("params"),
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        return es_json
