from dateutil import parser
from logging import Logger

from flask import request, jsonify
from flask_restful import Resource, abort
import requests

from pbench.server import PbenchServerConfig
from pbench.server.api.resources.query_apis import (
    get_es_url,
    get_index_prefix,
    gen_month_range,
    get_user_term,
)


class ControllersList(Resource):
    """
    Get the names of controllers within a date range.
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
        POST to search for Pbench controller names which have registered
        datasets within a specified date range and which are either owned
        by a specified username, or have been made publicly accessible.

        {
            "user": "username",
            "start": "start-time",
            "end": "end-time"
        }

        JSON parameters:
            user: specifies the owner of the data to be searched; it need not
                necessarily be the user represented by the session token
                header, assuming the session user is authorized to view "user"s
                data. If "user": None is specified, then only public datasets
                will be returned.

                TODO: When we have authorization infrastructure, we'll need to
                check that "session user" has rights to view "user" data. We might
                also default a missing "user" JSON field with the authorization
                token's user. This would require a different mechanism to signal
                "return public data"; for example, we could specify either
                "access": "public", "access": "private", or "access": "all" to
                include both private and public data.

            "start" and "end" are time strings representing a set of Elasticsearch
                run document indices in which to search.

        Returns a summary of the returned Elasticsearch query results, showing
        the Pbench controller name, the number of runs using that controller
        name, and the start timestamp of the latest run both in binary and
        string form:

        [
            {
                "key": "alphaville.example.com",
                "controller": "alphaville.example.com",
                "results": 2,
                "last_modified_value": 1598473155810.0,
                "last_modified_string": "2020-08-26T20:19:15.810Z"
            }
        ]
        """
        json_data = request.get_json(silent=True)
        if not json_data:
            self.logger.info("Invalid JSON object. Query: {}", request.url)
            abort(400, message="Invalid request payload")

        try:
            user = json_data["user"]
            start_arg = json_data["start"]
            end_arg = json_data["end"]
        except KeyError:
            keys = [k for k in ("user", "start", "end") if k not in json_data]
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
            "Discover controllers for user {}, prefix {}: ({} - {})",
            user,
            self.prefix,
            start,
            end,
        )

        payload = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": get_user_term(user)},
                        {"range": {"@timestamp": {"gte": start_arg, "lte": end_arg}}},
                    ]
                }
            },
            "size": 0,  # Don't return "hits", only aggregations
            "aggs": {
                "controllers": {
                    "terms": {"field": "run.controller", "order": [{"runs": "desc"}]},
                    "aggs": {"runs": {"max": {"field": "run.start"}}},
                }
            },
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
            controllers = []
            try:
                es_json = es_response.json()
                buckets = es_json["aggregations"]["controllers"]["buckets"]
                self.logger.info("{} controllers found", len(buckets))
                for controller in buckets:
                    c = {}
                    c["key"] = controller["key"]
                    c["controller"] = controller["key"]
                    c["results"] = controller["doc_count"]
                    c["last_modified_value"] = controller["runs"]["value"]
                    c["last_modified_string"] = controller["runs"]["value_as_string"]
                    controllers.append(c)
            except KeyError:
                self.logger.exception("ES response not formatted as expected")
                abort(500, message="INTERNAL ERROR")
            else:
                # construct response object
                return jsonify(controllers)
