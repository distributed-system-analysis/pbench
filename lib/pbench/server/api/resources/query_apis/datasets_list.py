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


class DatasetsList(Resource):
    """
    Get a list of dataset run documents for a controller.
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
        Get a list of datasets recorded for a particular controller and either
        owned by a specified username, or publicly accessible, within the set
        of Elasticsearch run indices defined by the date range.

        {
            "user": "username",
            "controller": "controller-name",
            "start": "start-time",
            "end": "end-time"
        }

        JSON parameters:
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

        Returns a list of run documents including the name, the associated
        controller, start and end timestamps:
        [
            {
                "key": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                "startUnixTimestamp": 1588178953561,
                "run.name": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                "run.controller": "dhcp31-187.example.com,
                "run.start": "2020-04-29T12:49:13.560620",
                "run.end": "2020-04-29T13:30:04.918704"
            }
        ]
        """
        json_data = request.get_json(silent=True)
        if not json_data:
            self.logger.info("Invalid JSON object. Query: {}", request.url)
            abort(400, message="Invalid request payload")

        try:
            user = json_data["user"]
            controller = json_data["controller"]
            start_arg = json_data["start"]
            end_arg = json_data["end"]
        except KeyError:
            keys = [
                k for k in ("user", "controller", "start", "end") if k not in json_data
            ]
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
            "Discover datasets for user {}, prefix {}: ({}: {} - {})",
            user,
            self.prefix,
            controller,
            start,
            end,
        )

        payload = {
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
                        {"term": get_user_term(user)},
                        {"term": {"run.controller": controller}},
                    ]
                }
            },
            "size": 5000,
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
            datasets = []
            try:
                es_json = es_response.json()
                hits = es_json["hits"]["hits"]
                self.logger.info("{} controllers found", len(hits))
                for dataset in hits:
                    src = dataset["_source"]
                    run = src["run"]
                    d = {
                        "key": run["name"],
                        "run.name": run["name"],
                        "run.controller": run["controller"],
                        "run.start": run["start"],
                        "run.end": run["end"],
                        "id": run["id"],
                    }
                    try:
                        timestamp = parser.parse(run["start"]).utcfromtimestamp()
                    except Exception as e:
                        self.logger.info(
                            "Can't parse start time {} to integer timestamp: {}",
                            run["start"],
                            e,
                        )
                        timestamp = dataset["sort"][0]

                    d["startUnixTimestamp"] = timestamp
                    if "config" in run:
                        d["run.config"] = run["config"]
                    if "prefix" in run:
                        d["run.prefix"] = run["prefix"]
                    if "@metadata" in src:
                        meta = src["@metadata"]
                        if "controller_dir" in meta:
                            d["@metadata.controller_dir"] = meta["controller_dir"]
                        if "satellite" in meta:
                            d["@metadata.satellite"] = meta["satellite"]
                    datasets.append(d)
            except KeyError:
                self.logger.exception("ES response not formatted as expected")
                abort(500, message="INTERNAL ERROR")
            else:
                # construct response object
                return jsonify(datasets)
