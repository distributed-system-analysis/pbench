from http import HTTPStatus
from logging import Logger
from typing import AnyStr

from flask import Response, jsonify
from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    JSON,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import CONTEXT, PostprocessError
from pbench.server.api.resources.query_apis.metadata_index import RunIdBase
from pbench.server.database.models.template import Template, TemplateNotFound


class TimeSeriesSamples(RunIdBase):
    """
    TimeSeries samples API that returns result-data document rows after
    applying client specified filters.
    """

    DOCUMENT_SIZE = 10000  # Number of documents to return in one page
    SCROLL_EXPIRY = "1m"  # Scroll id expires in 1 minute

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("filters", ParamType.JSON, required=False),
                Parameter("run_id", ParamType.STRING, required=True),
                Parameter("scroll_id", ParamType.STRING, required=False),
            ),
        )

    def get_mappings(self, index_name: AnyStr) -> JSON:
        template = Template.find(index_name)
        mappings = template.mappings
        result = {}
        for p, m in mappings["properties"].items():
            if m.get("type"):
                result[f"{p}"] = m["type"]
            elif m.get("properties"):
                for p_inner, m_inner in m["properties"].items():
                    result[f"{p}.{p_inner}"] = m_inner["type"]
        return result

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Construct a pbench Elasticsearch query for filtering result-data
        document samples based on a given run id and other filtering parameters
        specified in JSON payload.

        Note: If the ES scroll id is present we will ignore the filters
        parameter and instead construct an Elasticsearch query for scrolling
        based on a client provided scroll id.

        If a scroll_id is specified, the query will return the next page of
        results of the original query; otherwise we form a new query, either
        with the specified filters or without any filters (returning up to 10000
        documents at a time).

        Args:
            json_data:
                "run_id": run id of a dataset that client wants to search for
                        fetching the result-data document samples.

                "scroll_id": Server provided Elasticsearch scroll id that client
                            recieved in the result of the original query with
                            filters. This can be used to fetch the next page of
                            the result.

                "filters": key-value representation of query filter parameters to
                           narrow the search results e.g. {"sample.name": "sample1"}

        EXAMPLES:
            {
                "run_id": "1234567"
                "filters": {"sample.name": "sample1"},
            }
            or
            {
                "run_id": "1234567"
                "scroll_id": "cmFuZG9tX3Njcm9sbF9pZF9zdHJpbmdfMg=="
            }
        """
        run_id = context["run_id"]
        dataset = context["dataset"]
        scroll_id = json_data.get("scroll_id")

        self.logger.info(
            "Return TimeSeries sample rows {} for dataset {}, prefix {}, "
            "run id {} next page "
            if scroll_id
            else "",
            dataset,
            self.prefix,
            run_id,
        )

        scroll_id = json_data.get("scroll_id")
        if scroll_id:
            return {
                "path": "/_search/scroll",
                "kwargs": {
                    "json": {
                        "scroll": TimeSeriesSamples.SCROLL_EXPIRY,
                        "scroll_id": scroll_id,
                    }
                },
            }

        # Retrieve the ES indices that belong to this run_id
        indices = self.get_index(dataset, "result-data")
        if not indices:
            self.logger.debug(
                f"Found no indices matching the prefix result-data"
                f"for a dataset {dataset!r}"
            )
            abort(HTTPStatus.NOT_FOUND, message="Found no matching indices")

        try:
            # Retrive result-data mappings for validating user provided filters
            mappings = self.get_mappings("result-data")
        except (TemplateNotFound, KeyError) as e:
            self.logger.exception(f"Exception while getting 'result-data' template {e}")
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        es_filter = [{"match": {"run.id": run_id}}]
        query_strings = []

        # Validate each user provided filters against the result-data document
        # mappings. If the filter is not present in result-data mappings
        # properties we will not apply that filter in the ES query.
        for filter, value in json_data.get("filters", {}).items():
            if filter in mappings.keys() and mappings[filter] == "keyword":
                # Get all the keyword filters to apply
                es_filter.append({"match": {filter: value}})
            elif filter in mappings.keys() and mappings[filter] != "keyword":
                # Get all the text filters to apply
                # Note: There is only one text field sample.measurement_title
                # in result-data documents and if we can re-index it as a
                # keyword we can get rid of this loop.
                query_strings.append(
                    {"query_string": {"fields": f"{filter}", "query": f"{value}"}}
                )

        return {
            "path": f"/{indices}/_search?scroll={TimeSeriesSamples.SCROLL_EXPIRY}",
            "kwargs": {
                "json": {
                    "size": TimeSeriesSamples.DOCUMENT_SIZE,
                    "query": {"bool": {"filter": es_filter, "must": query_strings}},
                    "sort": [
                        {"sample.start": {"order": "asc", "unmapped_type": "long"}}
                    ],
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> Response:
        """
        Returns a Flask Response containing a JSON object with keys as
        results and possibly a scroll_id if the next page of results
        is available.

        If there are more than 10,000 documents available for the given filters, then
        we return the first 10,000 documents along with a scroll id which the client
        can use to request the next 10,000 documents.

        If there are no more than 10000 documents then we only return results
        without any scroll id.

        Example:
            {
                "scroll_id": "Scroll_id_string", # conditional
                "results": [
                    {
                        "@timestamp": "2020-09-03T01:58:58.712889",
                        "@timestamp_original": "1626277442035",
                        "result_data_sample_parent": "d8ec0b9d6affc5b638169db8b4cbbda2",
                        "run": {...},
                        "iteration": {...},
                        "sample": {...},
                        "result": {...}
                    },
                    {
                        "@timestamp": "2021-03-03T01:58:58.712889",
                        "@timestamp_original": "1626277442038",
                        "result_data_sample_parent": "d8ec0b9d6affc5b638169db8b4cbbda2",
                        "run": {...},
                        "iteration": {...},
                        "sample": {...},
                        "result": {...}
                    },
                    ...
                ]
            }

        """
        try:
            count = int(es_json["hits"]["total"]["value"])
            if count == 0:
                self.logger.info("No data returned by Elasticsearch")
                return jsonify({})

            results = [hit["_source"] for hit in es_json["hits"]["hits"]]
            ret_val = {"results": results}

            if (
                count > TimeSeriesSamples.DOCUMENT_SIZE
                and len(es_json["hits"]["hits"]) == TimeSeriesSamples.DOCUMENT_SIZE
            ):
                ret_val["scroll_id"] = es_json["_scroll_id"]

            return jsonify(ret_val)

        except KeyError as e:
            raise PostprocessError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Can't find Elasticsearch match data {e} in {es_json!r}",
            )
        except ValueError as e:
            raise PostprocessError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Conversion error {e} in {es_json!r}",
            )
