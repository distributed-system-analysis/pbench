from http import HTTPStatus

from flask import current_app, jsonify

from pbench.server import JSON, OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    ApiMethod,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import (
    ApiContext,
    ElasticBase,
    PostprocessError,
)
from pbench.server.utils import UtcTimeHelper


class DatasetsSearch(ElasticBase):
    """
    Pbench ES query API that returns run-data document sample rows after
    applying client specified search term within specified start and end time.
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.POST,
                OperationCode.READ,
                body_schema=Schema(
                    Parameter("user", ParamType.USER, required=False),
                    Parameter("start", ParamType.DATE, required=True),
                    Parameter("end", ParamType.DATE, required=True),
                    Parameter("search_term", ParamType.STRING, required=False),
                    Parameter(
                        "fields",
                        ParamType.LIST,
                        element_type=ParamType.STRING,
                        required=False,
                    ),
                ),
            ),
        )

    def assemble(self, params: ApiParams, context: ApiContext) -> JSON:
        """
        Construct a pbench search query based on a pattern matching given "search_term" parameter
        within a specified date range and which are either owned by a specified username,
        or have been made publicly accessible.

        {
            "user": "username",
            "start": "start-time",
            "end": "end-time"
            "search_term": "string_pattern_to_search"
            "fields": list(interested run document fields returned from IndexMapping API)
        }

        params: JSON dictionaries of type-normalized parameters
            user: specifies the owner of the data to be searched; it need not
                necessarily be the user represented by the session token
                header, assuming the session user is authorized to view "user"s
                data. If "user" is `null` (`None`) or unspecified, then only public datasets
                will be returned.

            "start" and "end" are datetime objects representing a set of Elasticsearch
                run document indices in which to search.

            "search_term": string pattern to match against all the datasets owned by a specified
                    username within a given time range

            "fields": List of run document fields end user is interested in. E.g.
                    ["@timestamp", "run.controller", "run.name", ...]
                    The fields controls what fields are returned by the query, and it has no effect
                    on which fields are searched.
        """
        user = params.body.get("user")
        access = params.body.get("access")
        start = params.body.get("start")
        end = params.body.get("end")

        # If the search_term parameter is not specified we will return all the Elasticsearch hits
        search_term = params.body.get("search_term", "")
        # If no fields are specified, the query will return all the fields from Elasticsearch hits
        selected_fields = params.body.get("fields", [])

        start_arg = UtcTimeHelper(start).to_iso_string()
        end_arg = UtcTimeHelper(end).to_iso_string()

        current_app.logger.info(
            "Search query for user {}, prefix {}: ({} - {}) on query: {}",
            user,
            self.prefix,
            start,
            end,
            search_term,
        )

        uri_fragment = self._gen_month_range("run", start, end)
        current_app.logger.info("fragment, {}", uri_fragment)
        return {
            "path": f"/{uri_fragment}/_search",
            "kwargs": {
                "json": {
                    "query": self._build_elasticsearch_query(
                        user,
                        access,
                        [
                            {
                                "range": {
                                    "@timestamp": {"gte": start_arg, "lte": end_arg}
                                }
                            },
                            {"query_string": {"query": f"*{search_term}*"}},
                        ],
                    ),
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "_source": {"include": selected_fields},
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: ApiContext) -> JSON:
        """
        Returns a summary of the returned Elasticsearch query results, showing
        the list of dictionaries with user selected fields from request json as keys
        Note: id field is added by server by default whereas other fields are client-selected.

        [
            {
                "id": "1c25e9f5b5dfc1ffb732931bf3899878",
                "@timestamp": "2021-07-12T22:44:19.562354",
                "run": {
                    "controller": "dhcp31-171.example.com",
                    "name": "pbench-user-benchmark_npalaska-dhcp31-171_2021.07.12T22.44.19",
                },
                "@metadata": {
                    "controller_dir": "dhcp31-171.example.com"
                }
            },
        ]
        """
        # If there are no matches for the user, query, and time range,
        # return the empty list rather than failing.
        try:
            count = es_json["hits"]["total"]["value"]
            if int(count) == 0:
                current_app.logger.info("No data returned by Elasticsearch")
                return jsonify([])
        except KeyError as e:
            raise PostprocessError(
                HTTPStatus.BAD_REQUEST,
                f"Can't find Elasticsearch match data {e} in {es_json!r}",
            )
        except ValueError as e:
            raise PostprocessError(
                HTTPStatus.BAD_REQUEST, f"Elasticsearch hit count {count!r} value: {e}"
            )
        results = []
        for hit in es_json["hits"]["hits"]:
            s = hit["_source"]
            s["id"] = hit["_id"]
            results.append(s)
        # construct response object
        return jsonify(results)
