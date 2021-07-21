from http import HTTPStatus
from logging import Logger

from flask import jsonify

from pbench.server import PbenchServerConfig
from pbench.server.api.resources.query_apis import (
    CONTEXT,
    ElasticBase,
    JSON,
    Parameter,
    ParamType,
    PostprocessError,
    Schema,
)


class IndexSearch(ElasticBase):
    """
    Create a search request based on given query parameter.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("user", ParamType.USER, required=False),
                Parameter("start", ParamType.DATE, required=True),
                Parameter("end", ParamType.DATE, required=True),
                Parameter("search_term", ParamType.STRING, required=False),
                Parameter("fields", ParamType.LIST, required=False),
            ),
        )

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
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

        json_data: JSON dictionary of type-normalized parameters
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
        user = json_data.get("user")
        start = json_data.get("start")
        end = json_data.get("end")

        # If the search_term parameter is not specified we will return all the Elasticsearch hits
        search_term = json_data.get("search_term", "")
        # If no fields are specified, the query will return all the fields from Elasticsearch hits
        selected_fields = json_data.get("fields", [])

        # We need to pass string dates as part of the Elasticsearch query; we
        # use the unconverted strings passed by the caller rather than the
        # adjusted and normalized datetime objects for this.
        start_arg = f"{start:%Y-%m-%d}"
        end_arg = f"{end:%Y-%m-%d}"

        self.logger.info(
            "Search query for user {}, prefix {}: ({} - {}) on query: {}",
            user,
            self.prefix,
            start,
            end,
            search_term,
        )

        uri_fragment = self._gen_month_range("run", start, end)
        self.logger.info("fragment, {}", uri_fragment)
        return {
            "path": f"/{uri_fragment}/_search",
            "kwargs": {
                "json": {
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": self._get_user_term(json_data)},
                                {
                                    "range": {
                                        "@timestamp": {"gte": start_arg, "lte": end_arg}
                                    }
                                },
                                {"query_string": {"query": f"*{search_term}*"}},
                            ]
                        }
                    },
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "_source": {"include": selected_fields},
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
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
                self.logger.info("No data returned by Elasticsearch")
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
