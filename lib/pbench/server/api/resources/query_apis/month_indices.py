from flask import jsonify
from logging import Logger
from typing import Any, AnyStr, Dict

from pbench.server import PbenchServerConfig
from pbench.server.api.resources.query_apis import ElasticBase, Schema


class MonthIndices(ElasticBase):
    """
    Get the range of dates in which datasets exist.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(config, logger, Schema())

    def assemble(self, json_data: Dict[AnyStr, Any]) -> Dict[AnyStr, Any]:
        """
        Report the month suffixes for run data indices.

        NOTE: No authorization or input parameters are required for this API,
        and there is no JSON query to form.
        """
        return {"path": "/_aliases", "kwargs": {}}

    def postprocess(self, es_json: Dict[AnyStr, Any]) -> Dict[AnyStr, Any]:
        months = []
        target = f"{self.prefix}.v6.run-data."
        self.logger.info("looking for {} in {}", target, es_json)
        for index in es_json.keys():
            if target in index:
                months.append(index.split(".")[-1])
        months.sort(reverse=True)
        self.logger.info("found months {!r}", months)
        # construct response object
        return jsonify(months)
