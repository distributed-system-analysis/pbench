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
    Abstracted Pbench API to get date-bounded controller data.
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
        POST for Pbench controllers with datasets within the specified date
        range, and owned by a specified user:

        {
            "user": "username",
            "start": "start-time",
            "end": "end-time"
        }

        "user" specifies the owner of the data to be searched; it need not
        necessarily be the user represented by the session token header,
        assuming the session user is authorized to view "user"s data. This
        will be used to constrain the Elasticsearch query.

        TODO: When we have authorization infrastructure, we'll need to
        check that "session user" has rights to view "user" data. We might
        also default a missing "user" JSON field with the authorization
        token's user.

        "start" and "end" are time strings representing a set of Elasticsearch
        run document indices in which to search.

        Required headers include

        Authorization:  Pbench session authorization token authorized to access
                        "user"'s data. E.g., "user", "admin" or a user with
                        whom the dataset has been shared.
        Content-Type:   application/json
        Accept:         application/json

        Return payload is a summary of the "aggregations" property of the
        returned Elasticsearch query results, showing the Pbench controller
        name, the number of runs using that controller name, and the start
        timestamp of the latest run both in binary and string form.

        TODO: Do we automatically return all "public" controllers, or should
        this be a separate parameter? E.g., when "I" log in, do I see all my
        own datasets *plus* all published/public controllers owned by others,
        or should that be a separate option (e.g., a checkbox on the view?)

        TODO: Similarly, a query from an unlogged-in session in the dashboard
        would presumably show datasets with "user": "public"; but does it show
        all datasets with "access": "public" as well?

        NOTE: This is the format currently constructed by the Pbench
        dashboard `src/model/dashboard.js` fetchControllers method, which
        becomes part of the Redux state.

        [
            {
                "key": "alphaville.usersys.redhat.com",
                "controller": "alphaville.usersys.redhat.com",
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

        # We need to support a query for public data without requiring
        # authorization; however if an Authorization header is given,
        # it must be of recommended JWT "Bearer" schema, and have a
        # non-empty token.
        #
        # TODO: validate the token with the user management object.
        authorization = request.headers.get("Authorization")
        session_token = None
        if authorization:
            type, token = authorization.split()
            if type.lower() == "bearer":
                session_token = token

            if not session_token:
                self.logger.warn(
                    '"Authorization" header specifies unsupported or missing '
                    ' schema; use "Authorization: Bearer <JWT-token>"'
                )
                abort(401, message="invalid user authorization")

        try:
            start = parser.parse(start_arg).replace(day=1)
            end = parser.parse(end_arg).replace(day=1)
        except Exception as e:
            self.logger.info(
                "Invalid start or end time string: {}, {}: {}", start_arg, end_arg, e
            )
            abort(400, message="Invalid start or end time string")

        # We have nothing to authorize against yet, but print the specified
        # user and session token to prove we got them.
        self.logger.info(
            "Discover controllers for user {}, prefix {}, authorization {}: ({} - {})",
            user,
            self.prefix,
            session_token,
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

        # TODO: the big assumption here involves the index version we're
        # referencing. While it's possible the root index name could change
        # at some point, advancing the version is going to happen more
        # often.
        #
        # So ... do we need to change the code here each time? The old
        # dashboard config is hardcoded for each version, so one option is
        # to add a version for each index to the pbench-server.cfg file.
        #
        # When we have a full live Python server, persisting the template
        # information in Redis or postgreSQL probably makes sense; maybe
        # we just hardcode until then?
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
