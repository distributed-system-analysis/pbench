from flask import jsonify
from flask_restful import Resource, abort
import requests

from pbench.server.api.resources.query_apis import get_es_url, get_index_prefix


class QueryMonthIndices(Resource):
    """
    Abstracted Pbench API to get date-bounded controller data.
    """

    def __init__(self, config, logger):
        self.logger = logger
        self.es_url = get_es_url(config)
        self.prefix = get_index_prefix(config)

    def get(self):
        """
        GET to detect the month suffixes existing for run data indices.

        Required headers include

        Content-Type:   application/json
        Accept:         application/json

        The return payload is a list of "YYYY-mm" date strings corresponding
        to the months in which tarballs were indexed into the appropriate
        `run-data` index. (E.g., `drb.v6.run-data.2020-11`). Note that this
        list is in DESCENDING order, so the earliest date is last.

        NOTE: No authorization or input payload is required for this API.

        NOTE: This is the format currently constructed by the Pbench
        dashboard `src/model/datastore.js` fetchMonthIndices method, which
        becomes part of the Redux state.

        [
            "2020-12",
            "2020-11",
            "2020-04"
        ]
        """
        self.logger.info(
            "QueryMonthIndices GET for prefix {}", self.prefix,
        )

        uri = f"{self.es_url}/_aliases"
        try:
            # query Elasticsearch
            es_response = requests.get(uri, headers={"Accept": "application/json"})
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
            months = []
            target = f"{self.prefix}.v6.run-data."
            try:
                es_json = es_response.json()
                self.logger.info("looking for {} in {}", target, es_json)
                for index in es_json.keys():
                    if target in index:
                        months.append(index.split(".")[-1])
                # The dashboard converts the strings to int (removing the '-')
                # and does a numeric sort; however since we always have a full
                # "YYYY-mm" date, this isn't necessary.
                months.sort(reverse=True)
                self.logger.info("found months {!r}", months)
            except KeyError:
                self.logger.exception("ES response not formatted as expected")
                abort(500, message="INTERNAL ERROR")
            else:
                # construct response object
                return jsonify(months)
