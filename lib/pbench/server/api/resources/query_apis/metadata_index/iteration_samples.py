from http import HTTPStatus
from logging import Logger
from typing import AnyStr, List, Union

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


class IterationSampleNamespace(RunIdBase):
    """
    Iteration samples API that returns namespace for each whitelisted
    result-data-sample subdocuments as well as lists of available values for
    each name.
    """

    WHITELIST_AGGS_FIELDS = ["run", "sample", "iteration", "benchmark"]

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(Parameter("run_id", ParamType.STRING, required=True)),
        )

    def get_keyword_fields(
        self, mappings: JSON, prefix: AnyStr = "", result: Union[List, None] = None
    ) -> List:
        if result is None:
            result = []
        if "properties" in mappings:
            for p, m in mappings["properties"].items():
                self.get_keyword_fields(m, f"{prefix}{p}.", result)
        elif mappings.get("type") == "keyword":
            result.append(prefix[:-1])  # Remove the trailing dot, if any
        else:
            for f, v in mappings.get("fields", {}).items():
                self.get_keyword_fields(v, f"{prefix}{f}.", result)
        return result

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Construct a pbench Elasticsearch query for aggregating a list of
        values for keyword fields mentioned in the WHITELIST_AGGS_FIELDS
        sub-documents of result-data-sample index document that belong to the
        given run id.

        Args:
            json_data: JSON dictionary of type-normalized parameters
                "run_id": Dataset document ID

        EXAMPLE:
        {
            "run_id": "1234567890"
        }
        """
        run_id = context["run_id"]
        dataset = context["dataset"]

        self.logger.info(
            "Return iteration sample namespace for dataset {}, prefix {}, " "run id {}",
            dataset,
            self.prefix,
            run_id,
        )

        # Retrieve the ES indices that belong to this run_id from the metadata
        # table
        indices = self.get_index(dataset, "result-data-sample")

        try:
            template = Template.find("result-data-sample")
        except TemplateNotFound:
            self.logger.exception(
                "Document template 'result-data-sample' not found in the database."
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="Mapping not found")

        # Only keep the whitelisted fields for aggregation
        mappings = {
            "properties": {
                key: value
                for key, value in template.mappings["properties"].items()
                if key in IterationSampleNamespace.WHITELIST_AGGS_FIELDS
            }
        }

        # Get all the fields from result-data-sample document mapping that
        # are of type keyword
        result = self.get_keyword_fields(mappings)

        # Build ES aggregation query for getting the iteration samples
        # namespaces
        aggs = {key: {"terms": {"field": key}} for key in result}

        return {
            "path": f"/{indices}/_search",
            "kwargs": {
                "json": {
                    "size": 0,
                    "query": {"bool": {"filter": {"match": {"run.id": run_id}}}},
                    "aggs": aggs,
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> Response:
        """
        Returns a Flask Response containing a JSON object (keyword/value
        pairs) where each key is the fully qualified dot-separated name of a
        keyword (sub-)field (from result-data-sample documents) and
        corresponding value is a non-empty list of values which appear in
        that field.

        Example:
            {
               "benchmark.name":["uperf"],
               "benchmark.primary_metric":["Gb_sec"],
               "benchmark.protocol":["tcp"],
               "benchmark.test_type":["stream"],
               "benchmark.uid":[
                  "benchmark_name:uperf-controller_host:hostname.com"
               ],
               "benchmark.uid_tmpl":[
                  "benchmark_name:%benchmark_name%-controller_host:%controller_host%"
               ],
               "iteration.name":[
                  "1-tcp_stream-131072B-2i",
                  "1-tcp_stream-131072B-2i-fail1",
                  "1-tcp_stream-131072B-2i-fail2",
                  "1-tcp_stream-131072B-2i-fail3",
                  "1-tcp_stream-131072B-2i-fail4"
               ],
               "run.config":["run-config"],
               "run.controller":["controller-name.com"],
               "run.id":["f3a37c9891a78886639e3bc00e3c5c4e"],
               "run.name":["uperf"],
               "run.script":["uperf"],
               "sample.client_hostname":[
                  "127.0.0.1",
                  "all"
               ],
               "sample.measurement_title.raw":["Gb_sec"],
               "sample.measurement_type":["throughput"],
               "sample.name":[
                  "sample1",
                  "sample2",
                  "sample3",
                  "sample4",
                  "sample5"
               ],
               "sample.server_hostname":[
                  "127.0.0.1",
                  "all"
               ],
               "sample.uid":[
                  "client_hostname:127.0.0.1-server_hostname:127.0.0.1-server_port:20010",
                  "client_hostname:all-server_hostname:all-server_port:all"
               ],
               "sample.uid_tmpl":[
                  "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%"
               ]
            }
        """
        try:
            new_json = {
                key: [bucket["key"] for bucket in agg["buckets"]]
                for key, agg in es_json["aggregations"].items()
                if agg["buckets"]
            }
            return jsonify(new_json)
        except KeyError as e:
            raise PostprocessError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Can't find Elasticsearch match data '{e}' in {es_json!r}",
            )


class IterationSamplesRows(RunIdBase):
    """
    Iteration samples API that returns iteration sample rows after
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

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Construct a pbench Elasticsearch query for filtering iteration
        samples based on a given run id and other filtering parameters
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
                        fetching the iteration samples.

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
            "Return iteration sample rows {} for dataset {}, prefix {}, run id {}",
            "next page " if scroll_id else "",
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
                        "scroll": IterationSamplesRows.SCROLL_EXPIRY,
                        "scroll_id": scroll_id,
                    }
                },
            }

        # Retrieve the ES indices that belong to this run_id
        indices = self.get_index(dataset, "result-data-sample")

        es_filter = [{"match": {"run.id": run_id}}]
        for filter, value in json_data.get("filters", {}).items():
            es_filter.append({"match": {filter: value}})

        return {
            "path": f"/{indices}/_search?scroll={IterationSamplesRows.SCROLL_EXPIRY}",
            "kwargs": {
                "json": {
                    "size": IterationSamplesRows.DOCUMENT_SIZE,
                    "query": {"bool": {"filter": es_filter}},
                    "sort": [
                        {"iteration.number": {"order": "asc", "unmapped_type": "long"}}
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
                        "run": {...},
                        "iteration": {...},
                        "benchmark": {...},
                        "sample": {...}
                    },
                    {
                        "@timestamp": "2021-03-03T01:58:58.712889",
                        "run": {...},
                        "iteration": {...},
                        "benchmark": {...},
                        "sample": {...},
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
                count > IterationSamplesRows.DOCUMENT_SIZE
                and len(es_json["hits"]["hits"]) == IterationSamplesRows.DOCUMENT_SIZE
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
