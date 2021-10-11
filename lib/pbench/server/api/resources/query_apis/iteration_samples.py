from flask import jsonify
from http import HTTPStatus
from logging import Logger

from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.auth import Auth
from pbench.server.api.resources import (
    JSON,
    Schema,
    Parameter,
    ParamType,
    PostprocessError,
)
from pbench.server.api.resources.query_apis import CONTEXT, ElasticBase
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.users import User
from pbench.server.database.models.template import Template, TemplateNotFound


class IterationSamples(ElasticBase):
    """
    Create iteration samples aggregation based on a given run id.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(Parameter("run_id", ParamType.STRING, required=True),),
        )

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Query the Dataset associated with this run id, and determine whether the
        authenticated user has READ access to this dataset. (Currently, this
        means the authenticated user is the owner of the dataset, or has ADMIN
        role.)
        If the user has authorization to read the dataset, return the Dataset
        object as CONTEXT so that the postprocess operation can proceed to get all
        the iteration aggregations.
        """
        run_id = client_json.get("run_id")

        # Query the dataset using the given run id
        dataset = Dataset.query(md5=run_id)
        if not dataset:
            self.logger.error("Dataset with Run ID {} not found", run_id)
            abort(HTTPStatus.NOT_FOUND, message="Dataset not found")

        owner = User.query(id=dataset.owner_id)
        if not owner:
            self.logger.error(
                "Dataset owner ID {} cannot be found in Users", dataset.owner_id
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="Dataset owner not found")

        # For Iteration samples, we check authorization against the ownership of the
        # dataset that was selected rather than having an explicit "user"
        # JSON parameter. This will raise UnauthorizedAccess on failure.
        self._check_authorization(owner.username, dataset.access)

        # The dataset exists, and authenticated user has enough access so continue
        # the operation with the appropriate CONTEXT.
        return {"dataset": dataset, "run_id": run_id}


class IterationSampleRows(IterationSamples):
    """
    Note: This is a first part of queryIterationSamples API that returns only unique rows
    for each subdocument.

    This class inherits the common IterationSamples class and builds an aggregated query
    against a user supplied run id to compile the filter header which shows every unique
    field in the 'benchmark', 'sample', 'iterations' and other subdocuments.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config, logger,
        )

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Construct a pbench search query for aggregating unique values for keyword fields in the
        'benchmark', 'sample', 'iterations' and other sub-documents of result-data-sample index document
        that belong to the given run id.
        {
            "run_id": "run id string"
        }
        json_data: JSON dictionary of type-normalized parameters
            "run_id": String representation of run id
        """
        run_id = context.get("run_id")
        dataset = context.get("dataset")

        self.logger.info(
            "Return sample iteration rows for user {}, prefix {}: for run id: {}",
            Auth.token_auth.current_user().username,
            self.prefix,
            run_id,
        )

        # Retrieve the ES indix that belongs to this run_id from the metadata table
        try:
            index_map = Metadata.getvalue(dataset=dataset, key="server.index-map")
            for key, values in index_map.items():
                if run_id in values:
                    index = key
                    self.logger.debug("Iteration samples index, {}", index)
        except MetadataError as e:
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

        if index_map is None:
            abort(
                HTTPStatus.BAD_REQUEST, message=f"Dataset {controller}>{name} not found"
            )

        try:
            template = Template.find("result-data-sample")
            mappings = template.mappings
        except TemplateNotFound:
            self.logger.exception(
                "Document template {} not found in the database.", index_name
            )
            abort(HTTPStatus.NOT_FOUND, message="Mapping not found")

        # Get all the fields from result-data-sample index that are of type keyword
        result = []
        for property in mappings["properties"]:
            if "properties" in mappings["properties"][property]:
                for sub_property in mappings["properties"][property]["properties"]:
                    if (
                        mappings["properties"][property]["properties"][
                            sub_property
                        ].get("type")
                        == "keyword"
                    ):
                        result.append(f"{property}.{sub_property}")

        # Special case: sample.measurement_title is of type `text` which is not available for aggregation.
        # However, we have added a "keyword" overlay to allow it to be aggregated such as:
        # "measurement_title": {"type": text", "fields": {"raw": {"type": "keyword"}}}
        result.append("sample.measurement_title.raw")

        # Build ES aggregation query for number of rows aggregations
        aggs = {}
        for key in result:
            aggs[key] = {"terms": {"field": key}}

        return {
            "path": f"/{index}/_search",
            "kwargs": {
                "json": {
                    "size": 0,
                    "query": {
                        "bool": {"filter": [{"match": {"run.id": f"{run_id}"}},]}
                    },
                    "aggs": aggs,
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        """
        Returns a list of aggregated unique values for keyword fields in the
        'benchmark', 'sample', 'iterations' and other subdocuments of result-data-sample index.

        Example:
            {
               "authorization.access":[],
               "authorization.owner":[],
               "benchmark.bs":[],
               "benchmark.clocksource":[],
               "benchmark.duplicate_packet_failure_mode":[],
               "benchmark.iodepth":[],
               "benchmark.ioengine":[],
               "benchmark.loss_granularity":[],
               "benchmark.name":["uperf"],
               "benchmark.negative_packet_loss_mode":[],
               "benchmark.numjobs":[],
               "benchmark.primary_metric":["Gb_sec"],
               "benchmark.protocol":["tcp"],
               "benchmark.rate_tolerance_failure":[],
               "benchmark.rw":[],
               "benchmark.sync":[],
               "benchmark.test_type":["stream"],
               "benchmark.traffic_direction":[],
               "benchmark.traffic_generator":[],
               "benchmark.trafficgen_uid":[],
               "benchmark.trafficgen_uid_tmpl":[],
               "benchmark.trial_mode":[],
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
               "run.toolsgroup":[],
               "run.user":[],
               "sample.category":[],
               "sample.client_hostname":[
                  "127.0.0.1",
                  "all"
               ],
               "sample.field":[],
               "sample.group":[],
               "sample.measurement_title.raw":["Gb_sec"],
               "sample.measurement_type":["throughput"],
               "sample.name":[
                  "sample1",
                  "sample2",
                  "sample3",
                  "sample4",
                  "sample5"
               ],
               "sample.pgid":[],
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
            es_json_aggs = es_json["aggregations"]
            new_json = {}
            for key, agg in es_json_aggs.items():
                new_json[key] = [bucket["key"] for bucket in agg["buckets"]]
            return jsonify(new_json)
        except KeyError as e:
            raise PostprocessError(
                HTTPStatus.BAD_REQUEST,
                f"Can't find Elasticsearch match data '{e}' in {es_json!r}",
            )
