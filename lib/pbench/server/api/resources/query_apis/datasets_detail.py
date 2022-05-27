from http import HTTPStatus
from flask import jsonify
from logging import Logger

from pbench.server import PbenchServerConfig, JSON
from pbench.server.api.resources import (
    API_METHOD,
    API_OPERATION,
    APIAbort,
    ApiParams,
    ApiSchema,
    ParamType,
    Parameter,
    Schema,
)
from pbench.server.api.resources.query_apis import (
    CONTEXT,
    ElasticBase,
    PostprocessError,
)
from pbench.server.database.models.datasets import (
    DatasetNotFound,
    Metadata,
    MetadataError,
)


class DatasetsDetail(ElasticBase):
    """
    Get detailed data from the run document for a dataset by name.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            ApiSchema(
                API_METHOD.POST,
                API_OPERATION.READ,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.STRING, required=True)
                ),
                body_schema=Schema(
                    Parameter("user", ParamType.USER, required=False),
                    Parameter("access", ParamType.ACCESS, required=False),
                    Parameter("start", ParamType.DATE, required=True),
                    Parameter("end", ParamType.DATE, required=True),
                    Parameter(
                        "metadata",
                        ParamType.LIST,
                        element_type=ParamType.KEYWORD,
                        keywords=ElasticBase.METADATA,
                    ),
                ),
            ),
        )

    def assemble(self, params: ApiParams, context: CONTEXT) -> JSON:
        """
        Get details for a specific Pbench dataset which is either owned
        by a specified username, or has been made publicly accessible.

        POST /datasets/detail/<dataset>
        {
            "user": "username",
            "start": "start-time",
            "end": "end-time",
            "metadata": ["seen", "saved"]
        }

        params: API parameter set

            URI parameters:
                "dataset" is the name of a Pbench agent dataset (tarball).

            JSON body parameters:
                user: specifies the owner of the data to be searched; it need not
                    necessarily be the user represented by the session token
                    header, assuming the session user is authorized to view "user"s
                    data. If "user": None is specified, then only public datasets
                    will be returned.

                "start" and "end" are time strings representing a set of Elasticsearch
                    run document indices in which the dataset will be found.

                "metadata" specifies the set of Dataset metadata properties the
                    caller needs to see. (If not specified, no metadata will be
                    returned.)

        context: Context passed from preprocess method: used to propagate the
            requested set of metadata to the postprocess method.
        """
        dataset = params.uri.get("dataset")
        user = params.body.get("user")
        access = params.body.get("access")
        start = params.body.get("start")
        end = params.body.get("end")

        # Copy client's metadata request to CONTEXT for postprocessor
        context["metadata"] = params.body.get("metadata")
        self.logger.info(
            "Return dataset {} for user {}, prefix {}: ({} - {})",
            dataset,
            user,
            self.prefix,
            start,
            end,
        )

        uri_fragment = self._gen_month_range("run", start, end)
        return {
            "path": f"/{uri_fragment}/_search",
            "kwargs": {
                "params": {"ignore_unavailable": "true"},
                "json": {
                    "query": self._build_elasticsearch_query(
                        user, access, [{"term": {"run.name": dataset}}]
                    ),
                    "sort": "_index",
                },
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        """
        Returns details from the run, @metadata, and host_tools_info subdocuments
        of the Elasticsearch run document. The Elasticsearch information can
        be enriched with Dataset DB metadata based on the "metadata" JSON
        parameter values, if specified.

        [
            {
                "runMetadata": {
                    "file-name": "/pbench/archive/fs-version-001/dhcp31-187.example.com/fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13.tar.xz",
                    "file-size": 216319392,
                    "md5": "12fb1e952fd826727810868c9327254f",
                    [...]
                },
                "hostTools": [
                    {
                        "hostname": "dhcp31-187",
                        "tools": {
                            "iostat": "--interval=3",
                            [...]
                        }
                    },
                ],
                "serverMetadata": {
                    "server.deletion": "2222-02-22",
                    "dashboard.saved": False,
                    "dataset.access": "public"
                }
            }
        ]
        """
        hits = es_json["hits"]["hits"]

        # NOTE: we're expecting just one. We're matching by just the
        # dataset name, which ought to be unique.
        if len(hits) == 0:
            raise PostprocessError(
                HTTPStatus.BAD_REQUEST, "The specified dataset has gone missing"
            )
        elif len(hits) > 1:
            raise PostprocessError(
                HTTPStatus.BAD_REQUEST, "Too many hits for a unique query"
            )
        src = hits[0]["_source"]

        # We're merging the "run" and "@metadata" sub-documents into
        # one dictionary, and then tacking on the host tools info in
        # its original form.
        run_metadata = src["run"]
        run_metadata.update(src["@metadata"])
        result = {
            "runMetadata": run_metadata,
            "hostTools": src["host_tools_info"],
        }

        try:
            m = self._get_metadata(src["run"]["name"], context["metadata"])
        except DatasetNotFound:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST, f"Dataset {src['run']['name']} not found"
            )
        except MetadataError as e:
            raise APIAbort(HTTPStatus.BAD_REQUEST, str(e))

        if m:
            result["serverMetadata"] = m

        # construct response object
        return jsonify(result)
