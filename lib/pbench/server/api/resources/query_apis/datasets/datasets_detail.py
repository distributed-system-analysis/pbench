from http import HTTPStatus

from flask import jsonify

from pbench.server import JSON, OperationCode
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiMethod,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import ApiContext, PostprocessError
from pbench.server.api.resources.query_apis.datasets import IndexMapBase
from pbench.server.database.models.dataset import (
    Dataset,
    DatasetNotFound,
    Metadata,
    MetadataError,
)


class DatasetsDetail(IndexMapBase):
    """
    Get detailed data from the run document for a dataset by name.
    """

    endpoint = "datasets_detail"
    urls = ["datasets/detail/<string:dataset>"]

    def __init__(self):
        super().__init__(
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True)
                ),
                query_schema=Schema(
                    Parameter(
                        "metadata",
                        ParamType.LIST,
                        element_type=ParamType.KEYWORD,
                        keywords=Metadata.METADATA_KEYS,
                        key_path=True,
                        string_list=",",
                    ),
                ),
                authorization=ApiAuthorizationType.DATASET,
            ),
        )

    def assemble(self, params: ApiParams, context: ApiContext) -> JSON:
        """
        Get details for a specific Pbench dataset which is either owned
        by a specified username, or has been made publicly accessible.

        GET /datasets/detail/<dataset>?metadata=global.seen,server.deletion

        params: API parameter set

            URI parameters:
                "dataset" is the name of a Pbench agent dataset (tarball).

            Query parameters:
                "metadata" specifies the set of Dataset metadata properties the
                    caller needs to see. (If not specified, no metadata will be
                    returned.)

        context: Context passed from preprocess method: used to propagate the
            requested set of metadata to the postprocess method.
        """
        dataset = context["dataset"]

        # Copy client's metadata request to CONTEXT for postprocessor
        context["metadata"] = params.query.get("metadata")

        indices = self.get_index(dataset, "run-data")

        return {
            "path": f"/{indices}/_search",
            "kwargs": {
                "params": {"ignore_unavailable": "true"},
                "json": {
                    "query": {"term": {"run.id": dataset.resource_id}},
                    "sort": "_index",
                },
            },
        }

    def postprocess(self, es_json: JSON, context: ApiContext) -> JSON:
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
            dataset = Dataset.query(resource_id=(src["run"]["id"]))
            m = self._get_dataset_metadata(dataset, context["metadata"])
        except DatasetNotFound:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST, f"Dataset {src['run']['id']} not found"
            )
        except MetadataError as e:
            raise APIAbort(HTTPStatus.BAD_REQUEST, str(e))

        if m:
            result["serverMetadata"] = m

        # construct response object
        return jsonify(result)
