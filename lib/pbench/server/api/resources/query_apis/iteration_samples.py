from http import HTTPStatus
from logging import Logger
from typing import AnyStr, Dict, List

from flask import Response, jsonify
from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    JSON,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import (
    CONTEXT,
    ElasticBase,
    PostprocessError,
)
from pbench.server.database.models.datasets import Dataset, Metadata, MetadataError
from pbench.server.database.models.template import Template, TemplateNotFound
from pbench.server.database.models.users import User


class IterationSamples(ElasticBase):
    """
    Create iteration samples aggregation based on a given run id.
    """

    WHITELIST_AGGS_FIELDS = ["run", "sample", "iteration", "benchmark"]

    def __init__(self, config: PbenchServerConfig, logger: Logger, schema: Schema):
        super().__init__(config, logger, schema)

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Query the Dataset associated with this run id, and determine whether the
        request is authorized for this dataset.

        If the user has authorization to read the dataset, return the Dataset
        object as CONTEXT so that the postprocess operations can use it to
        identify the index to be searched from document index metadata.
        """
        run_id = client_json.get("run_id")

        # Query the dataset using the given run id
        dataset = Dataset.query(md5=run_id)
        if not dataset:
            self.logger.error(f"Dataset with Run ID {run_id!r} not found")
            abort(HTTPStatus.NOT_FOUND, message="Dataset not found")

        owner = User.query(id=dataset.owner_id)
        if not owner:
            self.logger.error(
                f"Dataset owner ID { dataset.owner_id!r} cannot be found in Users"
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="Dataset owner not found")

        # For Iteration samples, we check authorization against the ownership of the
        # dataset that was selected rather than having an explicit "user"
        # JSON parameter. This will raise UnauthorizedAccess on failure.
        self._check_authorization(owner.username, dataset.access)

        # The dataset exists, and authenticated user has enough access so continue
        # the operation with the appropriate CONTEXT.
        return {"dataset": dataset, "run_id": run_id}

    def get_index(self, dataset):
        """
        Retrieve the ES index from the metadata table
        """
        try:
            index_map = Metadata.getvalue(dataset=dataset, key="server.index-map")
            index_keys = [key for key in index_map if "result-data-sample" in key]
        except MetadataError as e:
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

        if len(index_keys) != 1:
            self.logger.error(
                f"Found irregular result-data-sample indices {index_keys!r} "
                f"for a dataset {dataset.controller!r}|{dataset.name!r}"
            )
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                message="Encountered irregular index pattern",
            )
        index = index_keys[0]
        self.logger.debug(f"Iteration samples index, {index!r}")
        return index


class IterationSampleNamespace(IterationSamples):
    """
    Iteration samples API that returns namespace for each whitelisted
    result-data-sample subdocuments as well as lists of available values for
    each name.

    This class inherits the common IterationSamples class and builds an
    aggregated term query filtered by user supplied run id.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(Parameter("run_id", ParamType.STRING, required=True)),
        )

    def get_keyword_fields(self, mappings: Dict) -> List:
        fields = []

        def recurse(prefix: AnyStr, mappings: JSON, result: List):
            if "properties" in mappings:
                for p, m in mappings["properties"].items():
                    recurse(f"{prefix}{p}.", m, result)
            elif mappings.get("type") == "keyword":
                result.append(prefix[:-1])  # Remove the trailing dot, if any
            else:
                for f, v in mappings.get("fields", {}).items():
                    recurse(f"{prefix}{f}.", v, result)

        recurse("", mappings, fields)
        return fields

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Construct a pbench search query for aggregating a list of values for
        keyword fields mentioned in the WHITELIST_AGGS_FIELDS sub-documents
        of result-data-sample index document that belong to the
        given run id.

        {
            "run_id": "run id string"
        }

        json_data: JSON dictionary of type-normalized parameters
            "run_id": String representation of run id
        """
        run_id = context.get("run_id")
        dataset = context.get("dataset")

        self.logger.info(
            "Return iteration sample namespace for dataset {}|{}, prefix {}, "
            "run id {}",
            dataset.controller,
            dataset.name,
            self.prefix,
            run_id,
        )

        # Retrieve the ES index that belongs to this run_id from the metadata
        # table
        index = self.get_index(dataset)

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
                if key in IterationSamples.WHITELIST_AGGS_FIELDS
            }
        }

        # Get all the fields from result-data-sample index that are of type keyword
        result = self.get_keyword_fields(mappings)

        # Build ES aggregation query for number of rows aggregations
        aggs = {}
        for key in result:
            aggs[key] = {"terms": {"field": key}}

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
        Returns a stringified JSON object containing keyword/value pairs where
        each key is the fully qualified dot-separated name of a keyword
        (sub-)field (from result-data-sample documents) and corresponding value
        is a non-empty list of values which appear in that field.

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


class IterationSamplesRows(IterationSamples):
    """
       Iteration samples API that returns iteration sample rows after
       applying client specified filters.

       This class inherits the common IterationSamples class and builds ES
       query filtered by user supplied run id and other client supplied
       filtering parameters.
       """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("filters", ParamType.DICT, required=False),
                Parameter("run_id", ParamType.STRING, required=True),
                Parameter("scroll_id", ParamType.STRING, required=False),
            ),
        )

    def scroll_assemble(self, scroll_id: str, context: CONTEXT) -> JSON:
        """
        Construct a pbench search query for scrolling based on a client
        provided unexpired scroll id.

        "scroll_id": String representation of ES scroll id
        """
        dataset = context.get("dataset")
        run_id = context.get("run_id")

        self.logger.info(
            "Return iteration sample rows for dataset {}|{}, prefix {}, "
            "run id {}, scroll id {}",
            dataset.controller,
            dataset.name,
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
        Construct a pbench search query for filtering iteration samples of
        given run id and other filtering parameters mention in JSON payload.

        Note: If the ES scroll id is present we will skip the filters parameter
        and call scroll_assemble instead to scroll the next ES results page
        using the given scroll id.

        If the scroll_id and filters both are absent from the client JSON
        payload, we will return the first page of ES results (up to 10000
        documents) matching the given run id. If there are more than 10000
        documents available we will return the ES scroll id along with
        the other result back to client which the client can send back as
        scroll_id parameter if they want more data.

        {
            "scroll_id": "Server provided scroll id"
            "filters": "key-value representation of query filter parameters",
            "run_id": "run id string"
        }

        json_data:
            "run_id": String representation of run id,
            "filters": "key-value representation of query filter parameters",
        """
        if json_data.get("scroll_id"):
            return self.scroll_assemble(json_data.get("scroll_id"), context)
        filters = json_data.get("filters")
        run_id = json_data.get("run_id")
        dataset = context.get("dataset")

        self.logger.info(
            "Return iteration sample rows for dataset {}|{}, prefix {}, " "run id {}",
            dataset.controller,
            dataset.name,
            self.prefix,
            run_id,
        )

        # Retrieve the ES index that belongs to this run_id from the metadata
        # table
        index = self.get_index(dataset)

        es_filter = [{"match": {"run.id": run_id}}]
        if filters:
            for filter in filters:
                es_filter.append({"match": {filter: filters[filter]}})

        return {
            "path": f"/{index}/_search?scroll=1m",
            "kwargs": {
                "json": {
                    "size": 10000,  # The maximum default size
                    "query": {"bool": {"filter": es_filter}},
                    "sort": [
                        {
                            "iteration.number": {
                                "order": "asc",
                                "unmapped_type": "boolean",
                            }
                        }
                    ],
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT):
        """
        Returns a stringified JSON object containing keys as results and
        possibly scroll_id if the next page of results available.

        Like Elasticsearch if there are more than 10000 documents available
        for the given filters then we return the 10000 documents along with
        scroll id (This scroll id can be used to send back to get next batch
        of documents).

        If there are less than 10000 documents then we only return results
        without any scroll id.

        Example:
            {
                results: [
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
                ],
                "scroll_id": "Scroll_id_string" # conditional
            }

        """
        try:
            scroll_id = None
            count = es_json["hits"]["total"]["value"]
            if int(count) == 0:
                self.logger.info("No data returned by Elasticsearch")
                return jsonify([])
            if int(count) == 10000:
                scroll_id = es_json["_scroll_id"]

            results = []
            for hit in es_json["hits"]["hits"]:
                s = hit["_source"]
                results.append(s)
            if scroll_id:
                return jsonify({"scroll_id": scroll_id, "results": results})
            else:
                return jsonify({"results": results})

        except KeyError as e:
            raise PostprocessError(
                HTTPStatus.BAD_REQUEST,
                f"Can't find Elasticsearch match data {e} in {es_json!r}",
            )
