from flask import jsonify
from logging import Logger
from typing import Any, AnyStr, Dict

from pbench.server import PbenchServerConfig
from pbench.server.api.resources.query_apis import (
    ElasticBase,
    Schema,
    Parameter,
    ParamType,
    PostprocessError,
)


class ControllersList(ElasticBase):
    """
    Get the names of controllers within a date range.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("user", ParamType.USER, required=False),
                Parameter("start", ParamType.DATE, required=True),
                Parameter("end", ParamType.DATE, required=True),
            ),
        )

    def assemble(self, json_data: Dict[AnyStr, Any]) -> Dict[AnyStr, Any]:
        """
        Construct a search for Pbench controller names which have registered
        datasets within a specified date range and which are either owned
        by a specified username, or have been made publicly accessible.

        {
            "user": "username",
            "start": "start-time",
            "end": "end-time"
        }

        json_data: JSON dictionary of type-normalized parameters
            user: specifies the owner of the data to be searched; it need not
                necessarily be the user represented by the session token
                header, assuming the session user is authorized to view "user"s
                data. If "user": None is specified, then only public datasets
                will be returned.

                TODO: When we have authorization infrastructure, we'll need to
                check that "session user" has rights to view "user" data. We might
                also default a missing "user" JSON field with the authorization
                token's user. This would require a different mechanism to signal
                "return public data"; for example, we could specify either
                "access": "public", "access": "private", or "access": "all" to
                include both private and public data.

            "start" and "end" are datetime objects representing a set of Elasticsearch
                run document indices in which to search.
        """
        user = json_data.get("user")
        start = json_data.get("start")
        end = json_data.get("end")

        # We need to pass string dates as part of the Elasticsearch query; we
        # use the unconverted strings passed by the caller rather than the
        # adjusted and normalized datetime objects for this.
        start_arg = f"{start:%Y-%m}"
        end_arg = f"{end:%Y-%m}"

        self.logger.info(
            "Discover controllers for user {}, prefix {}: ({} - {})",
            user,
            self.prefix,
            start,
            end,
        )

        uri_fragment = self._gen_month_range("run", start, end)
        return {
            "path": f"/{uri_fragment}/_search",
            "kwargs": {
                "json": {
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": self._get_user_term(user)},
                                {
                                    "range": {
                                        "@timestamp": {"gte": start_arg, "lte": end_arg}
                                    }
                                },
                            ]
                        }
                    },
                    "size": 0,  # Don't return "hits", only aggregations
                    "aggs": {
                        "controllers": {
                            "terms": {
                                "field": "run.controller",
                                "order": [{"runs": "desc"}],
                            },
                            "aggs": {"runs": {"max": {"field": "run.start"}}},
                        }
                    },
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: Dict[AnyStr, Any]) -> Dict[AnyStr, Any]:
        """
        Returns a summary of the returned Elasticsearch query results, showing
        the Pbench controller name, the number of runs using that controller
        name, and the start timestamp of the latest run both in binary and
        string form:

        [
            {
                "key": "alphaville.example.com",
                "controller": "alphaville.example.com",
                "results": 2,
                "last_modified_value": 1598473155810.0,
                "last_modified_string": "2020-08-26T20:19:15.810Z"
            }
        ]
        """
        controllers = []
        # If there are no matches for the user, controller name,
        # and time range, return the empty list rather than failing.
        # Note that we can't check the length of ["hits"]["hits"]
        # because we've told Elasticsearch to return only aggregations,
        # not source documents.
        try:
            count = es_json["hits"]["total"]["value"]
            if int(count) == 0:
                self.logger.warning("No data returned by Elasticsearch")
                return jsonify(controllers)
        except KeyError as e:
            raise PostprocessError(
                f"Can't find Elasticsearch match data {e} in {es_json!r}"
            )
        except ValueError as e:
            raise PostprocessError(f"Elasticsearch hit count {count!r} value: {e}")
        buckets = es_json["aggregations"]["controllers"]["buckets"]
        self.logger.info("{} controllers found", len(buckets))
        for controller in buckets:
            c = {}
            c["key"] = controller["key"]
            c["controller"] = controller["key"]
            c["results"] = controller["doc_count"]
            c["last_modified_value"] = controller["runs"]["value"]
            c["last_modified_string"] = controller["runs"]["value_as_string"]
            controllers.append(c)
        # construct response object
        return jsonify(controllers)
