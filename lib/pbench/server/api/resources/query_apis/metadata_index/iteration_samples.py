from http import HTTPStatus
from logging import Logger
from typing import AnyStr, List

from flask import Response, jsonify
from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    JSON,
    Parameter,
    ParamType,
    PostprocessError,
    Schema,
)
from pbench.server.api.resources.query_apis import CONTEXT
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
        self, mappings: JSON, prefix: AnyStr = "", result: List = []
    ) -> List:
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

        {
            "run_id": "run id string"
        }

        json_data: JSON dictionary of type-normalized parameters
            "run_id": run id string
        """
        run_id = context["run_id"]
        dataset = context["dataset"]

        self.logger.info(
            "Return iteration sample namespace for dataset {}, prefix {}, " "run id {}",
            dataset,
            self.prefix,
            run_id,
        )

        # Retrieve the ES index that belongs to this run_id from the metadata
        # table
        index = self.get_index(dataset, "result-data-sample")

        try:
            template = Template.find("result-data-sample")
        except TemplateNotFound:
            self.logger.exception(
                "Document template 'result-data-sample' not found in the database."
            )
            abort(HTTPStatus.NOT_FOUND, message="Mapping not found")

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
            "path": f"/{index}/_search",
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

    def scroll_assemble(self, scroll_id: str, context: CONTEXT) -> JSON:
        """
        Construct a pbench Elasticsearch query for scrolling based on a client
        provided scroll id.

        Note: To get a valid result the scroll id need to be unexpired,
        Current expiry for the scroll id is 1 minute after client first
        recieves it from the server.

        "scroll_id": Elasticsearch scroll id
        """
        dataset = context["dataset"]
        run_id = context["run_id"]

        self.logger.info(
            "Return iteration sample rows for dataset {}, prefix {}, "
            "run id {}, scroll id {}",
            dataset,
            self.prefix,
            run_id,
            scroll_id,
        )

        return {
            "path": "/_search/scroll",
            "kwargs": {"json": {"scroll": "1m", "scroll_id": scroll_id}},
        }

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Construct a Elasticsearch query for filtering iteration samples of
        given run id and other filtering parameters mention in
        JSON payload.

        Note: If the ES scroll id is present we will ignore the filters
        parameter and instead construct a Elasticsearch query for scrolling
        based on a client provided scroll id.

        If a scroll_id is specified, we return the next page of the original
        query; otherwise we form a new query, either with the specified filters
        or without any filters (up to 10000 documents at a time).

        {
            "run_id": "run id string"
            "scroll_id": "Server provided scroll id"
            "filters": "key-value representation of query filter parameters",
        }

        json_data:
            "run_id": run id of a dataset that client wants to search for
                    fetching the iteration samples.

            "scroll_id": Server provided Elasticsearch scroll id that client
                        recieved in the result of the original query with
                        filters. This can be used to fetch the next page of
                        the result.

            "filters": key-value representation of query filter parameters to
                       narrow the search results e.g. {"sample.name": "sample1"}
        """
        run_id = context["run_id"]
        dataset = context["dataset"]

        self.logger.info(
            "Return iteration sample rows for dataset {}, prefix {}, run id {}",
            dataset,
            self.prefix,
            run_id,
        )

        scroll_id = json_data.get("scroll_id")
        if scroll_id:
            return {
                "path": "/_search/scroll",
                "kwargs": {"json": {"scroll": "1m", "scroll_id": scroll_id}},
            }

        # Retrieve the ES indices that belongs to this run_id
        index = self.get_index(dataset, "result-data-sample")

        es_filter = [{"match": {"run.id": run_id}}]
        for filter, value in json_data.get("filters", {}).items():
            es_filter.append({"match": {filter: value}})

        return {
            "path": f"/{index}/_search?scroll=1m",
            "kwargs": {
                "json": {
                    "size": 10000,  # The maximum number of documents returned
                    "query": {"bool": {"filter": es_filter}},
                    "sort": [
                        {"iteration.number": {"order": "asc", "unmapped_type": "long",}}
                    ],
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> Response:
        """
        Returns a Flask Response containing a JSON object with keys as
        results and possibly scroll_id if the next page of results available.

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
                        "run": {
                            "id": "58bed61de1fd6ce57d682c320c506c4a",
                            "controller": "controller.name.com",
                            "name": "benchmark name",
                            "script": "fio",
                            ...
                        },
                        "iteration": {
                            "name": "1-rw-4KiB",
                            "number": 1
                        },
                        "benchmark": {
                            "bs": "4k",
                            "clocksource": "gettimeofday",
                            "direct": "0",
                            "filename": "/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo",
                            "iodepth": "32",
                            "ioengine": "libaio",
                            "log_avg_msec": "1000",
                            "log_hist_msec": "10000",
                            ...
                        },
                        "sample": {
                            "client_hostname": "localhost-4",
                            "closest_sample": 1,
                            "description": "Average submission latency per I/O operation",
                            "mean": 2722310.79166667,
                            "role": "client",
                            "stddev": 0,
                            "stddevpct": 0,
                            "uid": "client_hostname:localhost-4",
                            "measurement_type": "latency",
                           ...
                        }
                    },
                    {
                        "@timestamp": "2021-03-03T01:58:58.712889",
                        "run": {
                            "id": "58bed61de1fd6ce57d682c320c506c4a",
                            "controller": "controller.name.com",
                            "name": "benchmark name",
                            "script": "fio",
                            ...
                        },
                        "iteration": {
                            "name": "1-rw-4KiB",
                            "number": 1
                        },
                        "benchmark": {
                            "bs": "4k",
                            "clocksource": "gettimeofday",
                            "direct": "0",
                            "filename": "/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo",
                            "iodepth": "32",
                            "ioengine": "libaio",
                            "log_avg_msec": "1000",
                            "log_hist_msec": "10000",
                            ...
                        },
                        "sample": {
                            "client_hostname": "localhost-4",
                            "closest_sample": 1,
                            "description": "Average completion latency per I/O operation",
                            "mean": 761676162.46875,
                            "role": "client",
                            "stddev": 0,
                            "stddevpct": 0,
                            ...
                    },
                    ...
                ]
            }

        """
        try:
            scroll_id = None
            count = es_json["hits"]["total"]["value"]
            if int(count) == 0:
                self.logger.info("No data returned by Elasticsearch")
                return jsonify({})
            if int(count) > 10000 and len(es_json["hits"]["hits"]) == 10000:
                scroll_id = es_json["_scroll_id"]

            results = [hit["_source"] for hit in es_json["hits"]["hits"]]
            ret_val = {"results": results}
            if scroll_id:
                ret_val["scroll_id"] = scroll_id
            return jsonify(ret_val)

        except KeyError as e:
            raise PostprocessError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Can't find Elasticsearch match data {e} in {es_json!r}",
            )
