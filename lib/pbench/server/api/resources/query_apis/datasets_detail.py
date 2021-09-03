from http import HTTPStatus
from flask import jsonify
from logging import Logger

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    JSON,
    Schema,
    Parameter,
    ParamType,
    PostprocessError,
)
from pbench.server.api.resources.query_apis import CONTEXT, ElasticBase


class DatasetsDetail(ElasticBase):
    """
    Get detailed data from the run document for a dataset by name.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("user", ParamType.USER, required=False),
                Parameter("access", ParamType.ACCESS, required=False),
                Parameter("name", ParamType.STRING, required=True),
                Parameter("start", ParamType.DATE, required=True),
                Parameter("end", ParamType.DATE, required=True),
            ),
        )

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Get details for a specific Pbench dataset which is either owned
        by a specified username, or has been made publicly accessible.

        {
            "user": "username",
            "name": "dataset-name",
            "start": "start-time",
            "end": "end-time"
        }

        json_data: JSON dictionary of type-normalized key-value pairs
            user: specifies the owner of the data to be searched; it need not
                necessarily be the user represented by the session token
                header, assuming the session user is authorized to view "user"s
                data. If "user": None is specified, then only public datasets
                will be returned.

            "name" is the name of a Pbench agent dataset (tarball).

            "start" and "end" are time strings representing a set of Elasticsearch
                run document indices in which the dataset will be found.

        context: Context passed from preprocess method: not used here.
        """
        user = json_data.get("user")
        name = json_data.get("name")
        start = json_data.get("start")
        end = json_data.get("end")
        self.logger.info(
            "Return dataset {} for user {}, prefix {}: ({} - {})",
            name,
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
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"run.name": name}},
                                {"term": self._get_user_term(json_data)},
                            ]
                        }
                    },
                    "sort": "_index",
                },
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        """
        Returns details from the run, @metadata, and host_tools_info subdocuments
        of the Elasticsearch run document:

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
                    }
                ]
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
        # construct response object
        return jsonify(result)
