from flask import request, jsonify
from flask_restful import Resource, abort
import requests

from dateutil import parser
from pbench.server.api.resources.query_apis import (
    get_es_url,
    get_index_prefix,
    gen_month_range,
)


class QueryResult(Resource):
    """
    Abstracted Pbench API to get detailed data for a particular
    dataset by name. The date range given isn't used for the search
    directly, but rather allows building a set of Elasticsearch index
    names that will contain the data. (Note that the dashboard uses the
    same date range it used to find controllers; however it could make this
    more efficient by using only the year and month in which the result
    was generated.)

    Note that although the name "queryResult" is retained for consistency
    with the existing dashboard UI code, the word "result" is a bit
    misleading in that this deals with Pbench "run" documents, not Pbench
    "results" documents. It's a follow-on to queryResults, which returns
    the list of datasets within a specified date range for a given controller
    (as reported by queryControllers). The queryResult API returns details from
    the dataset run document; basically the union of the "run" and "@metadata"
    sub-documents.
    """

    def __init__(self, config, logger):
        self.logger = logger
        self.es_url = get_es_url(config)
        self.prefix = get_index_prefix(config)

    def post(self):
        """
        POST to get details for a specific Pbench dataset within the
        specified date range, and owned by a specified user:

        {
            "user": "email-tag",
            "name": "dataset-name",
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
        token's user. (Or with the default user "public" if there's no
        token, indicating there's no logged-in user.)

        "name" is the name of a Pbench agent dataset (tarball).

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
        returned Elasticsearch query results, showing fields from the "run"
        subdocument, including the controller and name, the start and end
        time, and a starting UNIX timestamp.

        TODO: We probably need to return all *unowned* runs when called
        without a session token or user parameter. We need to define precisely
        how this should work.

        NOTE: This is the format currently constructed by the Pbench
        dashboard `src/model/dashboard.js` fetchResults method, which
        becomes part of the Redux state. The "runMetadata" is a join of
        the ES run document's "@metadata" and "run" sub-documents, while
        "hostTools" is the run document's "host_tools_info" nested array.

        [
            {
                "runMetadata": {
                    "file-name": "/pbench/archive/fs-version-001/dhcp31-187.perf.lab.eng.bos.redhat.com/fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13.tar.xz",
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
            abort(400, message="Missing request payload")

        try:
            user = json_data["user"]
            name = json_data["name"]
            start_arg = json_data["start"]
            end_arg = json_data["end"]
        except KeyError:
            keys = [k for k in ("user", "name", "start", "end") if k not in json_data]
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
        # user and session token to prove we got them (and so the variables
        # aren't diagnosed as "unused")
        self.logger.info(
            "QueryControllers POST for user {}, prefix {}, session {}: ({}: {} - {})",
            user,
            self.prefix,
            session_token,
            name,
            start,
            end,
        )

        payload = {
            "query": {
                "bool": {
                    "filter": [
                        {"match": {"run.name": name}},
                        {"match": {"authorization.user": user}},
                    ]
                }
            },
            "sort": "_index",
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
        except Exception as e:
            self.logger.exception(
                "Exception {!r} occurred during the Elasticsearch post request", e
            )
            abort(500, message="INTERNAL ERROR")
        else:
            run_metadata = {}
            try:
                es_json = es_response.json()
                hits = es_json["hits"]["hits"]

                # NOTE: we're expecting just one. We're matching by just the
                # dataset name, which ought to be unique.
                self.logger.info("{} datasets found", len(hits))
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
