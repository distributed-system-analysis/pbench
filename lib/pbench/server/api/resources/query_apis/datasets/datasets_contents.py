from http import HTTPStatus

from flask import current_app

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    ApiAuthorizationType,
    ApiMethod,
    ApiParams,
    ApiSchema,
    JSON,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.query_apis import ApiContext, PostprocessError
from pbench.server.api.resources.query_apis.datasets import IndexMapBase


class DatasetsContents(IndexMapBase):
    """
    Datasets Contents API returns the list of sub-directories and files
    present under a directory.
    """

    MAX_SIZE = 10000

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                uri_schema=Schema(
                    Parameter("dataset", ParamType.DATASET, required=True),
                    Parameter("target", ParamType.STRING, required=False),
                ),
                authorization=ApiAuthorizationType.DATASET,
            ),
        )

    def assemble(self, params: ApiParams, context: ApiContext) -> JSON:
        """
        Construct a pbench Elasticsearch query for getting a list of
        documents which contains the user provided parent with files
        and its sub-directories with metadata of run-toc index document
        that belong to the given run id.

        Args:
            params: ApiParams includes the uri parameters, which provide the dataset and target.
            context: propagate the dataset and the "target" directory value.
        """
        # Copy target directory metadata to CONTEXT for postprocessor
        target = "/" + params.uri.get("target", "")
        context["target"] = target

        dataset = context["dataset"]

        current_app.logger.info(
            "Discover dataset {} Contents, directory {}",
            dataset.name,
            target,
        )

        # Retrieve the ES indices that belong to this run_id from the metadata
        # table
        indices = self.get_index(dataset, "run-toc")

        return {
            "path": f"/{indices}/_search",
            "kwargs": {
                "json": {
                    "size": self.MAX_SIZE,
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "dis_max": {
                                        "queries": [
                                            {"term": {"directory": target}},
                                            {"term": {"parent": target}},
                                        ]
                                    }
                                },
                                {"term": {"run_data_parent": dataset.resource_id}},
                            ],
                            "must_not": {"regexp": {"directory": f"{target}/[^/]+/.+"}},
                        }
                    },
                }
            },
        }

    def postprocess(self, es_json: JSON, context: ApiContext) -> JSON:
        """
        Returns a JSON object (keyword/value pairs) whose values are lists of
        entries describing individual directories and files.

        Example: These are the contents of es_json parameter. The
        contents are the result of a request for directory "/1-default"

        {
            "took": 6,
            "timed_out": False,
            "_shards": {"total": 3, "successful": 3, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "max_score": 0.0,
                "hits": [
                    {
                        "_index": "riya-pbench.v6.run-toc.2021-05",
                        "_type": "_doc",
                        "_id": "d4a8cc7c4ecef7vshg4tjhrew174828d",
                        "_score": 0.0,
                        "_source": {
                            "parent": "/",
                            "directory": "/1-default",
                            "mtime": "2021-05-01T24:00:00",
                            "mode": "0o755",
                            "name": "1-default",
                            "files": [
                                {
                                    "name": "reference-result",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 0,
                                    "mode": "0o777",
                                    "type": "sym",
                                    "linkpath": "sample1",
                                }
                            ],
                            "run_data_parent": "ece030bdgfkjasdkf7435e6a7a6be804",
                            "authorization": {"owner": "1", "access": "private"},
                            "@timestamp": "2021-05-01T24:00:00",
                        },
                    },
                    {
                        "_index": "riya-pbench.v6.run-toc.2021-05",
                        "_type": "_doc",
                        "_id": "3bba25b62fhdgfajgsfdty6797ed06a",
                        "_score": 0.0,
                        "_source": {
                            "parent": "/1-default",
                            "directory": "/1-default/sample1",
                            "mtime": "2021-05-01T24:00:00",
                            "mode": "0o755",
                            "name": "sample1",
                            "ancestor_path_elements": ["1-default"],
                            "files": [
                                {
                                    "name": "result.txt",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 0,
                                    "mode": "0o644",
                                    "type": "reg",
                                },
                                {
                                    "name": "user-benchmark.cmd",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 114,
                                    "mode": "0o755",
                                    "type": "reg",
                                },
                            ],
                            "run_data_parent": "ece030bdgfkjasdkf7435e6a7a6be804",
                            "authorization": {"owner": "1", "access": "private"},
                            "@timestamp": "2021-05-01T24:00:00",
                        },
                    },
                ],
            },
        }

        Output:
            {
                "directories":
                [
                    {
                        "name": "sample1",
                        "uri": "https://host/api/v1/datasets/id/contents/1-default/sample1"
                    }
                ],
                "files": [
                    {
                        "name": "reference-result",
                        "mtime": "2021-05-01T24:00:00",
                        "size": 0,
                        "mode": "0o777",
                        "type": "sym",
                        "linkpath": "sample1",
                        "uri": "https://host/api/v1/datasets/id/inventory/1-default/reference-result"
                    }
                ]
            }
        """
        request = context["request"]
        resource_id = context["dataset"].resource_id
        target = context["target"]
        if len(es_json["hits"]["hits"]) == 0:
            raise PostprocessError(
                HTTPStatus.NOT_FOUND,
                f"No directory {target!r} in {resource_id!r} contents.",
            )

        prefix = current_app.server_config.rest_uri
        origin = f"{self._get_uri_base(request).host}{prefix}/datasets/{resource_id}"

        dir_list = []
        file_list = []
        for val in es_json["hits"]["hits"]:
            if val["_source"]["directory"] == target:
                # Retrieve files list if present else add an empty list.
                for f in val["_source"].get("files", []):
                    f["uri"] = f"{origin}/inventory{target}/{f['name']}"
                    file_list.append(f)
            elif val["_source"]["parent"] == target:
                name = val["_source"]["name"]
                dir_list.append(
                    {"name": name, "uri": f"{origin}/contents{target}/{name}"}
                )

        return {"directories": dir_list, "files": file_list}
