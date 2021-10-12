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
from pbench.server.database.models.datasets import Dataset, Metadata, MetadataError
from pbench.server.database.models.users import User
from pbench.server.database.models.template import Template, TemplateNotFound


class IterationSamples(ElasticBase):
    """
    Create iteration samples aggregation based on a given run id.
    """

    WHITELIST_AGGS_FIELDS = ["run", "sample", "iteration", "benchmark"]

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(Parameter("run_id", ParamType.STRING, required=True),),
        )

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Query the Dataset associated with this run id, and determine whether the
        request is authorized for this dataset.

        If the user has authorization to read the dataset, return the Dataset
        object as CONTEXT so that the postprocess operation can proceed to get all
        the iteration aggregations.
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


class IterationSampleRows(IterationSamples):
    """
    Iteration samples API that returns only unique rows for each subdocument.

    This class inherits the common IterationSamples class and builds an
    aggregated query against a user supplied run id to compile the filter header
    which shows every unique field in the 'benchmark', 'sample', 'iterations'
    and other subdocuments.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(config, logger)

    def get_keyword_fields(self, mappings):
        fields = []

        def recurse(prefix, mappings, result):
            if "properties" in mappings:
                for p, m in mappings["properties"].items():
                    recurse(f"{prefix}{p}.", m, result)
            elif mappings.get("type") == "keyword":
                result.append(prefix[:-1])  # Remove the trailing dot, if any
            elif mappings.get("type") == "text" and mappings.get("fields"):
                for field in mappings.get("fields"):
                    recurse(f"{prefix}{field}.", mappings.get("fields")[field], result)

        recurse("", mappings, fields)
        return fields

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Construct a pbench search query for aggregating unique values for keyword
        fields in the 'benchmark', 'sample', 'iterations' and other
        sub-documents of result-data-sample index document that belong to the
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
            "Return sample iteration rows for user {}, prefix {}: for run id: {}",
            Auth.token_auth.current_user().username,
            self.prefix,
            run_id,
        )

        # Retrieve the ES index that belongs to this run_id from the metadata
        # table
        try:
            index_map = Metadata.getvalue(dataset=dataset, key="server.index-map")
            for key, values in index_map.items():
                if run_id in values:
                    index = key
                    self.logger.debug(f"Iteration samples index, {index!r}")
        except MetadataError as e:
            abort(HTTPStatus.BAD_REQUEST, message=str(e))

        if index is None:
            abort(
                HTTPStatus.BAD_REQUEST,
                message=f"Dataset with run_id: {run_id!r} not found",
            )

        try:
            template = Template.find("result-data-sample")
            mappings = template.mappings

            # Only keep the whitelisted fields for aggregation
            for key in mappings["properties"].copy():
                if key not in IterationSamples.WHITELIST_AGGS_FIELDS:
                    del mappings["properties"][key]
        except TemplateNotFound:
            self.logger.exception(
                "Document template 'result-data-sample' not found in the database."
            )
            abort(HTTPStatus.NOT_FOUND, message="Mapping not found")

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
                    "query": {"bool": {"filter": {"match": {"run.id": f"{run_id}"}}}},
                    "aggs": aggs,
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        """
        Returns a non-empty list of aggregated unique values for keyword fields
        in the 'benchmark', 'sample', 'iterations' and 'run' subdocuments of
        result-data-sample index. The output only contains fields that has at
        least 1 unique value.

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
