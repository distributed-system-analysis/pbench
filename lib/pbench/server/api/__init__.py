"""
Pbench Server API module -
Provides middleware for remote clients, either the associated Pbench
Dashboard or any number of pbench agent users.
"""

import os
import sys
import hashlib
from pathlib import Path
import requests
import humanize

from flask import request, jsonify, Flask, make_response
from flask_restful import Resource, abort, Api
from werkzeug.utils import secure_filename

from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.common.exceptions import BadConfig
from pbench.server.utils import filesize_bytes

ALLOWED_EXTENSIONS = {"xz"}

app = None


def allowed_file(filename):
    """Check if the file has the correct extension."""
    try:
        fn = filename.rsplit(".", 1)[1].lower()
    except IndexError:
        return False
    allowed = "." in filename and fn in ALLOWED_EXTENSIONS
    return allowed


def register_endpoints(api, app):
    """Register flask endpoints with the corresponding resource classes
    to make the APIs active."""

    api.add_resource(Upload, f"{app.config['REST_URI']}/upload")
    api.add_resource(HostInfo, f"{app.config['REST_URI']}/host_info")
    api.add_resource(Elasticsearch, f"{app.config['REST_URI']}/elasticsearch")
    api.add_resource(GraphQL, f"{app.config['REST_URI']}/graphql")


def create_app():
    """Create Flask app with defined resource endpoints."""

    global app

    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        print(
            f"{__name__}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        config = PbenchServerConfig(cfg_name)
    except BadConfig as e:
        print(f"{__name__}: {e} (config file {cfg_name})", file=sys.stderr)
        sys.exit(1)

    app = Flask(__name__)
    api = Api(app)

    app.logger = get_pbench_logger(__name__, config)
    app.config_server = config.conf["pbench-server"]
    app.config_elasticsearch = config.conf["elasticsearch"]
    app.config_graphql = config.conf["graphql"]

    prdp = app.config_server.get("pbench-receive-dir-prefix")
    if not prdp:
        app.logger.error("Missing config variable for pbench-receive-dir-prefix")
        sys.exit(1)
    try:
        upload_directory = Path(f"{prdp}-002").resolve(strict=True)
    except FileNotFoundError:
        app.logger.exception("pbench-receive-dir-prefix does not exist on the host")
        sys.exit(1)
    except Exception:
        app.logger.exception(
            "Exception occurred during setting up the upload directory on the host"
        )
        sys.exit(1)
    else:
        app.upload_directory = upload_directory

    app.config["PORT"] = app.config_server.get("rest_port")
    app.config["VERSION"] = app.config_server.get("rest_version")
    app.config["MAX_CONTENT_LENGTH"] = filesize_bytes(
        app.config_server.get("rest_max_content_length")
    )
    app.config["REST_URI"] = app.config_server.get("rest_uri")
    app.config["LOG"] = app.config_server.get("rest_log")
    app.config["BIND_HOST"] = app.config_server.get("bind_host")
    app.config["WORKERS"] = app.config_server.get("workers")

    register_endpoints(api, app)

    return app


def _build_cors_preflight_response():
    response = make_response()
    response = _corsify_actual_response(response)
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response


def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


class CorsOptionsRequest:
    """
    From the client side, an OPTIONS request is initiated before every POST to request CORS.
    On the server side, the server must specify the response headers to grant CORS accordingly.
    """

    def __init__(self, options_exception_msg):
        self.options_exception_msg = options_exception_msg

    def options(self):
        try:
            response = _build_cors_preflight_response()
        except Exception:
            app.logger.exception(self.options_exception_msg)
            abort(400, message=self.options_exception_msg)
        response.status_code = 200
        return response


class GraphQL(Resource, CorsOptionsRequest):
    """GraphQL API for post request via server."""

    def __init__(self):
        CorsOptionsRequest.__init__(self, "Bad options request for the GraphQL query")

    def post(self):
        global app
        graphQL = f"{app.config_graphql.get('host')}:{app.config_graphql.get('port')}"
        json_data = request.get_json(silent=True)

        if not json_data:
            app.logger.error("GraphQL: Invalid json object %s", request.url)
            abort(400, message="GraphQL: Invalid json object in request")

        try:
            # query GraphQL
            response = requests.post(graphQL, json=json_data)

            # construct response object
            response = make_response(response.text)
            response = _corsify_actual_response(response)

        except requests.exceptions.ConnectionError:
            app.logger.exception("Connection refused during the GraphQL post request")
            abort(500, message="Network problem, could not post to GraphQL Endpoint")
        except requests.exceptions.Timeout:
            app.logger.exception("Connection timed out during the GraphQL post request")
            abort(
                500, message="Connection timed out, could not post to GraphQL Endpoint"
            )
        except requests.exceptions.InvalidURL:
            app.logger.exception("Invalid url during the GraphQL post request")
            abort(
                500, message="Invalid GraphQL url, could not complete the post request"
            )
        except Exception:
            app.logger.exception("Exception occurred during the GraphQL post request")
            abort(500, message="Could not post to GraphQL endpoint")

        response.status_code = 200
        return response


class Elasticsearch(Resource, CorsOptionsRequest):
    """Elasticsearch API for post request via server."""

    def __init__(self):
        CorsOptionsRequest.__init__(
            self, "Bad options request for the Elasticsearch query"
        )

    def post(self):
        global app
        elasticsearch = f"{app.config_elasticsearch.get('host')}:{app.config_elasticsearch.get('port')}"
        json_data = request.get_json(silent=True)
        if not json_data:
            app.logger.error(
                "Elasticsearch: Invalid json object. Query: %s", request.url
            )
            abort(400, message="Elasticsearch: Invalid json object in request")

        if not json_data["indices"]:
            app.logger.error("Elasticsearch: Missing indices path in the post request")
            abort(400, message="Missing indices path in the Elasticsearch request")

        try:
            # query Elasticsearch
            if "params" in json_data:
                url = f"{elasticsearch}/{json_data['indices']}?{json_data['params']}"
            else:
                url = f"{elasticsearch}/{json_data['indices']}"

            if "payload" in json_data:
                response = requests.post(url, json=json_data["payload"])
            else:
                app.logger.info(
                    "No payload found in Elasticsearch post request json data"
                )
                response = requests.get(url)

            # construct response object
            response = make_response(response.text)
            response = _corsify_actual_response(response)

        except requests.exceptions.ConnectionError:
            app.logger.exception(
                "Connection refused during the Elasticsearch post request"
            )
            abort(
                500, message="Network problem, could not post to Elasticsearch Endpoint"
            )
        except requests.exceptions.Timeout:
            app.logger.exception(
                "Connection timed out during the Elasticsearch post request"
            )
            abort(
                500,
                message="Connection timed out, could not post to Elasticsearch Endpoint",
            )
        except requests.exceptions.InvalidURL:
            app.logger.exception("Invalid url during the Elasticsearch post request")
            abort(
                500,
                message="Invalid Elasticsearch url, could not complete the post request",
            )
        except Exception:
            app.logger.exception(
                "Exception occurred during the Elasticsearch post request"
            )
            abort(
                500, message="Could not post to Elasticsearch endpoint",
            )

        response.status_code = 200
        return response


class HostInfo(Resource):
    def get(self):
        global app
        try:
            response = jsonify(
                dict(
                    message=f"{app.config_server.get('user')}@{app.config_server.get('host')}"
                    f":{app.config_server.get('pbench-receive-dir-prefix')}-002"
                )
            )
        except Exception:
            app.logger.exception("There was something wrong constructing the host info")
            abort(500, message="There was something wrong with your request")
        response.status_code = 200
        return response


class Upload(Resource):
    def post(self):
        global app
        if not request.headers.get("filename"):
            app.logger.debug(
                "Tarfile upload: Post operation failed due to missing filename header"
            )
            abort(
                400,
                message="Missing filename header, POST operation requires a filename header to name the uploaded file",
            )
        filename = secure_filename(request.headers.get("filename"))

        if not request.headers.get("md5sum"):
            app.logger.debug(
                f"Tarfile upload: Post operation failed due to missing md5sum header for file {filename}"
            )
            abort(
                400,
                message="Missing md5sum header, POST operation requires md5sum of an uploaded file in header",
            )
        md5sum = request.headers.get("md5sum")

        app.logger.debug("Receiving file: {}", filename)
        if not allowed_file(filename):
            app.logger.debug(
                f"Tarfile upload: Bad file extension received for file {filename}"
            )
            abort(400, message="File extension not supported. Only .xz")

        try:
            content_length = int(request.headers.get("Content-Length"))
        except ValueError:
            app.logger.debug(
                f"Tarfile upload: Invalid content-length header, not an integer for file {filename}"
            )
            abort(400, message="Invalid content-length header, not an integer")
        except Exception:
            app.logger.debug(
                f"Tarfile upload: No Content-Length header value found for file {filename}"
            )
            abort(400, message="Missing required content-length header")
        else:
            if content_length > app.config["MAX_CONTENT_LENGTH"]:
                app.logger.debug(
                    f"Tarfile upload: Content-Length exceeded maximum upload size allowed. File: {filename}"
                )
                abort(
                    400,
                    message=f"Payload body too large, {content_length:d} bytes, maximum size should be less than "
                    f"or equal to {humanize.naturalsize(app.config['MAX_CONTENT_LENGTH'])}",
                )
            elif content_length == 0:
                app.logger.debug(
                    f"Tarfile upload: Content-Length header value is 0 for file {filename}"
                )
                abort(
                    400,
                    message="Upload failed, Content-Length received in header is 0",
                )

        full_path = app.upload_directory / filename
        bytes_received = 0

        try:
            with open(full_path, "wb") as f:
                chunk_size = 4096
                app.logger.debug("Writing chunks")
                hash_md5 = hashlib.md5()

                while True:
                    chunk = request.stream.read(chunk_size)
                    bytes_received += len(chunk)
                    if len(chunk) == 0 or bytes_received > content_length:
                        break

                    f.write(chunk)
                    hash_md5.update(chunk)
        except Exception:
            app.logger.exception(
                "Tarfile upload: There was something wrong uploading {}", filename
            )
            abort(500, message=f"There was something wrong uploading {filename}")

        message = None
        if bytes_received != content_length:
            app.logger.debug(
                f"Tarfile upload: Bytes received does not match with content length header value for file {filename}"
            )
            message = (
                f"Bytes received ({bytes_received}) does not match with content length header"
                f" ({content_length}), upload failed"
            )

        elif hash_md5.hexdigest() != md5sum:
            app.logger.debug(f"Tarfile upload: md5sum check failed for file {filename}")
            message = f"md5sum check failed for {filename}, upload failed"

        if message:
            try:
                os.remove(full_path)
            except Exception as exc:
                app.logger.warning(
                    "Failed to remove compressed %s when trying to clean up: %s",
                    full_path,
                    exc,
                )
            abort(400, message=message)
        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = 201
        return response
