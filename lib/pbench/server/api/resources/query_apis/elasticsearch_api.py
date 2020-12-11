import requests
from flask_restful import Resource, abort
from flask import request, make_response
from pbench.server.api.resources.query_apis import get_es_url


class Elasticsearch(Resource):
    """Elasticsearch API for post request via server."""

    def __init__(self, config, logger):
        self.logger = logger
        self.elasticsearch = get_es_url(config)

    def post(self):
        json_data = request.get_json(silent=True)
        if not json_data:
            message = "Invalid json object in the query"
            self.logger.warning(f"{message}: {request.url}")
            abort(400, message=message)

        if not json_data["indices"]:
            message = "Missing indices path in the post request"
            self.logger.warning(f"{message}")
            abort(400, message=f"{message}")

        try:
            # query Elasticsearch
            if "params" in json_data:
                url = (
                    f"{self.elasticsearch}/{json_data['indices']}?{json_data['params']}"
                )
            else:
                url = f"{self.elasticsearch}/{json_data['indices']}"

            if "payload" in json_data:
                es_response = requests.post(url, json=json_data["payload"])
            else:
                self.logger.debug(
                    "No payload found in Elasticsearch post request json data"
                )
                es_response = requests.get(url)
            es_response.raise_for_status()

        except requests.exceptions.HTTPError as e:
            self.logger.exception("HTTP error {} from Elasticsearch post request", e)
            abort(es_response.status_code, message=f"HTTP error {e} from Elasticsearch")

        except requests.exceptions.ConnectionError:
            self.logger.exception(
                "Connection refused during the Elasticsearch post request"
            )
            abort(
                502, message="Network problem, could not post to Elasticsearch Endpoint"
            )
        except requests.exceptions.Timeout:
            self.logger.exception(
                "Connection timed out during the Elasticsearch post request"
            )
            abort(
                504,
                message="Connection timed out, could not post to Elasticsearch Endpoint",
            )
        except Exception:
            self.logger.exception(
                "Exception occurred during the Elasticsearch post request"
            )
            abort(
                500, message="INTERNAL ERROR",
            )

        try:
            # Construct our response object
            response = make_response(es_response.text)
        except Exception:
            self.logger.exception(
                "Exception occurred Elasticsearch response construction"
            )
            abort(
                500, message="INTERNAL ERROR",
            )

        response.status_code = es_response.status_code
        return response
