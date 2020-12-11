from flask import request, jsonify
from flask_restful import Resource, abort
import requests

from dateutil import parser, rrule
from pbench.server.api.resources.query_apis import get_es_url, get_index_prefix


class QueryControllers(Resource):
    """
    Abstracted Pbench API to get date-bounded controller data.
    """

    def __init__(self, config, logger):
        self.logger = logger
        self.es_url = get_es_url(config)
        self.prefix = get_index_prefix(config)

    @staticmethod
    def _genMonthUriRange(prefix, index, start, end):
        """
        _genMonthUriRange Construct a comma-separated list of index names
        qualified by year and month suitable for use in the Elasticsearch
        /_search query URI.

        The month is incremented by 1 from "start" to "end"; for example,

        _genMonthUriRange('drb.', 'v4.run.', '2020-08', '2020-10') will result
        in

            'drb.v4.run.2020-08,drb.v4.run.2020-09,drb.v4.run.2020-10,'

        This code is adapted from Javascript in the Pbench dashboard's
        'moment_constants.js' getAllMonthsWithinRange function.

        Args:
            prefix ([string]): The Pbench server index prefix
            index ([string]): The desired monthly index root
            start ([datetime.datetime]): The start time
            end ([datetime.datetime]): The end time

        Returns:
            [string]: A comma-separated list of month-qualified index names
        """
        monthResults = list()
        queryString = ""
        for m in rrule.rrule(rrule.MONTHLY, dtstart=start, until=end):
            monthResults.append(m.strftime("%Y-%m"))

        # TODO: hardcoding the index here is risky. We need a framework to
        # help the web services understand index versions and template
        # formats, probably by building a persistent database from the
        # index template documents at startup. This is TBD.
        for monthValue in monthResults:
            if index == "v4.result-data.":
                queryString += f"{prefix + index + monthValue}-*,"
            else:
                queryString += f"{prefix + index + monthValue},"
        return queryString

    def post(self):
        """
        POST for Pbench controller datasets with start times within the
        specified search range, and owned by a specified user:

        {
            "user": "email-tag",
            "start": "start-time",
            "end": "end-time"
        }

        "user" specifies the owner of the data to be searched; it need not
        necessarily be the user represented by the session token header,
        assuming the session user is authorized to view "user"s data. This
        will be used to constrain the Elasticsearch query.

        TODO: When we have authorization infrastructure, we'll need to
        check that "session user" has rights to view "user" data.

        "start" is a time string representing the starting range of dates
        to search.

        "end" is a time string representing the end range of dates to
        to search.

        The Elasticsearch URL string is also dependent upon the configured
        "prefix". This is a Pbench artifact that allows multiple Pbench
        instances to share a single Elasticsearch server, by segregating
        their data into unique namespaces. Each Pbench index name is
        qualified by the index_prefix of the Pbench server that originally
        indexed the data. The prefix comes from the pbench-server.cfg
        file for the server instance. For example, production, "staging",
        and development server instances might all share one Elasticsearch
        cluster by choosing unique prefixes to generate unique index
        names.

        Required headers include

        X-auth-token:   Pbench session authorization token authorized to access
                        "user"'s data. E.g., "user", "admin" or a user with
                        whom the dataset has been shared.
        Content-Type:   application/json
        Accept:         application/json

        Return payload is a summary of the "aggregations" property of the
        returned Elasticsearch query results, showing the Pbench controller
        name, the number of runs using that controller name, and the start
        timestamp of the latest run both in binary and string form.

        TODO: We probably need to return all *unowned* controllers when called
        without a session token or user parameter. We need to define precisely
        how this should work.

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
            abort(400, message="Missing request payload")

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
            start = parser.parse(start_arg)
            end = parser.parse(end_arg)
        except Exception as e:
            self.logger.info(
                "Invalid start or end time string: {}, {}: {}", start_arg, end_arg, e
            )
            abort(400, message="Invalid start or end time string")

        # We have nothing to authorize against yet, but print the specified
        # user and session token to prove we got them (and so the variables
        # aren't diagnosed as "unused")
        self.logger.info(
            "QueryControllers POST for user {}, prefix {}, session {}: ({} - {})",
            user,
            self.prefix,
            session_token,
            start,
            end,
        )

        # TODO: we could make this a constant template, then copy it and
        # replace the start and end times. Is that worthwhile?
        payload = {
            "query": {"range": {"@timestamp": {"gte": start_arg, "lte": end_arg}}},
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
        uri_fragment = QueryControllers._genMonthUriRange(
            self.prefix, ".v6.run-data.", start, end
        )

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
        except Exception as e:
            self.logger.exception(
                "Exception {!r} occurred during the Elasticsearch post request", e
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
