from http import HTTPStatus
from flask import jsonify
from flask_restful import abort
from logging import Logger

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import JSON, Schema, Parameter, ParamType
from pbench.server.api.resources.query_apis import CONTEXT, ElasticBase
from pbench.server.database.models.datasets import DatasetNotFound, MetadataError


class DatasetsList(ElasticBase):
    """
    Get a list of dataset run documents for a controller.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("user", ParamType.USER, required=False),
                Parameter("access", ParamType.ACCESS, required=False),
                Parameter("controller", ParamType.STRING, required=True),
                Parameter("start", ParamType.DATE, required=True),
                Parameter("end", ParamType.DATE, required=True),
                Parameter(
                    "metadata",
                    ParamType.LIST,
                    element_type=ParamType.KEYWORD,
                    keywords=ElasticBase.METADATA,
                ),
            ),
        )

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Get a list of datasets recorded for a particular controller and either
        owned by a specified username, or publicly accessible, within the set
        of Elasticsearch run indices defined by the date range.

        {
            "user": "username",
            "access": "private",
            "controller": "controller-name",
            "start": "start-time",
            "end": "end-time",
            "metadata": ["seen", "saved"]
        }

        json_data: JSON dictionary of type-normalized key-value pairs
            user: specifies the owner of the data to be searched; it need not
                necessarily be the user represented by the session token
                header, assuming the session user is authorized to view "user"s
                data. If "user": None is specified, then only public datasets
                will be returned.

            "controller" is the name of a Pbench agent controller (normally a
                host name).

            "start" and "end" are time strings representing a set of
                Elasticsearch run document indices in which the dataset will be
                found.

            "metadata" specifies the set of Dataset metadata properties the
                caller needs to see. (If not specified, no metadata will be
                returned.)

        context: Context passed from preprocess method: used to propagate the
            requested set of metadata to the postprocess method.
        """
        user = json_data.get("user")
        controller = json_data.get("controller")
        start = json_data.get("start")
        end = json_data.get("end")

        # Copy client's metadata request to CONTEXT for postprocessor
        context["metadata"] = json_data.get("metadata")

        self.logger.info(
            "Discover datasets for user {}, prefix {}: ({}: {} - {})",
            user,
            self.prefix,
            controller,
            start,
            end,
        )

        uri_fragment = self._gen_month_range("run", start, end)
        return {
            "path": f"/{uri_fragment}/_search",
            "kwargs": {
                "json": {
                    "_source": {
                        "includes": [
                            "@metadata.controller_dir",
                            "@metadata.satellite",
                            "run.controller",
                            "run.start",
                            "run.end",
                            "run.name",
                            "run.config",
                            "run.prefix",
                            "run.id",
                        ]
                    },
                    "sort": {"run.end": {"order": "desc"}},
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": self._get_user_term(json_data)},
                                {"term": {"run.controller": controller}},
                            ]
                        }
                    },
                    "size": 5000,
                },
                "params": {"ignore_unavailable": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        """
        Returns a list of run document summaries for the requested controller
        and user within the specified time range. The Elasticsearch information
        can be enriched with Dataset DB metadata based on the "metadata" JSON
        parameter values, if specified.

        {
            "dhcp31-187.example.com": [
                {
                    "startUnixTimestamp": 1588178953561,
                    "run.name": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                    "run.controller": "dhcp31-187.example.com",
                    "run.start": "2020-04-29T12:49:13.560620",
                    "run.end": "2020-04-29T13:30:04.918704",
                    "serverMetadata": {
                        "deletion": "2021-11-05",
                        "access": "private"
                    }
                }
            ]
        }
        """
        datasets = []
        hits = es_json["hits"]["hits"]
        self.logger.info("{} controllers found", len(hits))
        controller = None
        for dataset in hits:
            src = dataset["_source"]
            run = src["run"]
            if not controller:
                controller = run["controller"]
            elif controller != run["controller"]:
                self.logger.warning(
                    "Expected all controllers to match: {} and {} don't match",
                    controller,
                    run["controller"],
                )

            d = {
                "result": run["name"],
                "controller": run["controller"],
                "start": run["start"],
                "end": run["end"],
                "id": run["id"],
            }

            if "config" in run:
                d["config"] = run["config"]
            if "prefix" in run:
                d["run.prefix"] = run["prefix"]
            if "@metadata" in src:
                meta = src["@metadata"]
                if "controller_dir" in meta:
                    d["@metadata.controller_dir"] = meta["controller_dir"]
                if "satellite" in meta:
                    d["@metadata.satellite"] = meta["satellite"]

            try:
                m = self._get_metadata(
                    run["controller"], run["name"], context["metadata"]
                )
            except DatasetNotFound:
                abort(
                    HTTPStatus.BAD_REQUEST,
                    message=f"Dataset {src['run']['name']} not found",
                )
            except MetadataError as e:
                abort(HTTPStatus.BAD_REQUEST, message=str(e))

            if m:
                d["serverMetadata"] = m

            datasets.append(d)

        result = {controller: datasets}

        # construct response object
        return jsonify(result)
