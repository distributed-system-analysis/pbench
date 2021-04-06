from logging import Logger

from flask import request, jsonify
from flask_restful import Resource, abort
import requests

from dateutil import parser
from pbench.server import PbenchServerConfig
from pbench.server.api.resources.query_apis import (
    get_es_url,
    get_index_prefix,
    gen_month_range,
    get_user_term,
)


class DatasetsDetail(Resource):
    """
    Get detailed data from the run document for a dataset by name.
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        """
        __init__ Initialize the resource with info each call will need.

        Args:
            :config: The Pbench server config object
            :logger: a logger
        """
        self.logger = logger
        self.es_url = get_es_url(config)
        self.prefix = get_index_prefix(config)

    def post(self):
        """
        Get details for a specific Pbench dataset which is either owned
        by a specified username, or has been made publicly accessible.

        {
            "user": "username",
            "name": "dataset-name",
            "start": "start-time",
            "end": "end-time"
        }

        JSON parameters:
            user: specifies the owner of the data to be searched; it need not
                necessarily be the user represented by the session token
                header, assuming the session user is authorized to view "user"s
                data. If "user": None is specified, then only public datasets
                will be returned.

            "name" is the name of a Pbench agent dataset (tarball).

            "start" and "end" are time strings representing a set of Elasticsearch
                run document indices in which the dataset will be found.

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
        json_data = request.get_json(silent=True)
        if not json_data:
            self.logger.info("Invalid JSON object. Query: {}", request.url)
            abort(400, message="Invalid request payload")

        try:
            user = json_data["user"]
            name = json_data["name"]
            start_arg = json_data["start"]
            end_arg = json_data["end"]
        except KeyError:
            keys = [k for k in ("user", "name", "start", "end") if k not in json_data]
            self.logger.info("Missing required JSON keys {}", ",".join(keys))
            abort(400, message=f"Missing request data: {','.join(keys)}")

        try:
            start = parser.parse(start_arg).replace(day=1)
            end = parser.parse(end_arg).replace(day=1)
        except Exception as e:
            self.logger.info(
                "Invalid start or end time string: {}, {}: {}", start_arg, end_arg, e
            )
            abort(400, message="Invalid start or end time string")

        self.logger.info(
            "Return dataset {} for user {}, prefix {}: ({} - {})",
            name,
            user,
            self.prefix,
            start,
            end,
        )

        payload = {
            "query": {
                "bool": {
                    "filter": [
                        {"match": {"run.name": name}},
                        {"match": get_user_term(user)},
                    ]
                }
            },
            "sort": "_index",
        }

        # TODO: Need to refactor the template processing code from indexer.py
        # to maintain the essential indexing information in a persistent DB
        # (probably a Postgresql table) so that it can be shared here and by
        # the indexer without re-loading on each access. For now, the index
        # version is hardcoded.
        uri_fragment = gen_month_range(self.prefix, ".v6.run-data.", start, end)

        uri = f"{self.es_url}/{uri_fragment}/_search"
        try:
            # query Elasticsearch
            es_response = requests.post(
                uri,
                params={"ignore_unavailable": "true"},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )
            es_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.logger.exception("HTTP error {} from Elasticsearch post request", e)
            abort(502, message="INTERNAL ERROR")
        except requests.exceptions.ConnectionError:
            self.logger.exception(
                "Connection refused during the Elasticsearch post request"
            )
            abort(502, message="Network problem, could not post to Elasticsearch")
        except requests.exceptions.Timeout:
            self.logger.exception(
                "Connection timed out during the Elasticsearch post request"
            )
            abort(504, message="Connection timed out, could not post to Elasticsearch")
        except requests.exceptions.InvalidURL:
            self.logger.exception(
                "Invalid url {} during the Elasticsearch post request", uri
            )
            abort(500, message="INTERNAL ERROR")
        except Exception:
            self.logger.exception(
                "Exception occurred during the Elasticsearch post request"
            )
            abort(500, message="INTERNAL ERROR")
        else:
            run_metadata = {}
            try:
                es_json = es_response.json()
                hits = es_json["hits"]["hits"]

                # NOTE: we're expecting just one. We're matching by just the
                # dataset name, which ought to be unique.
                if len(hits) != 1:
                    self.logger.warn(
                        "{} datasets found: expected exactly 1!", len(hits)
                    )
                src = hits[0]["_source"]

                # We're merging the "run" and "@metadata" sub-documents into
                # one dictionary, and then tacking on the host tools info in
                # its original form.
                run_metadata.update(src["run"])
                run_metadata.update(src["@metadata"])
                result = {
                    "runMetadata": run_metadata,
                    "hostTools": src["host_tools_info"],
                }
            except KeyError:
                self.logger.exception("ES response not formatted as expected")
                abort(500, message="INTERNAL ERROR")
            else:
                # construct response object
                return jsonify(result)
