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
import tempfile

from flask import request, jsonify, Flask, make_response
from flask_restful import Resource, abort, Api
from werkzeug.utils import secure_filename

from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.common.exceptions import BadConfig
from pbench.server.utils import filesize_bytes

from pbench.server.api.resources.query_controllers import QueryControllers

ALLOWED_EXTENSIONS = {"xz"}


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

    base_uri = app.config["REST_URI"]
    app.logger.info("Registering service endpoints with base URI {}", base_uri)
    api.add_resource(
        Upload,
        f"{base_uri}/upload/ctrl/<string:controller>",
        resource_class_args=(app, api),
    )
    api.add_resource(
        QueryControllers,
        f"{base_uri}/controllers/list",
        resource_class_args=(app, api),
    )
    api.add_resource(HostInfo, f"{base_uri}/host_info", resource_class_args=(app, api))
    api.add_resource(
        Elasticsearch, f"{base_uri}/elasticsearch", resource_class_args=(app, api)
    )
    api.add_resource(GraphQL, f"{base_uri}/graphql", resource_class_args=(app, api))


def create_app():
    """Create Flask app with defined resource endpoints."""

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

    app.config["ES_URL"] = (
        "http://"
        + app.config_elasticsearch.get("host")
        + ":"
        + app.config_elasticsearch.get("port")
    )
    app.config["PORT"] = app.config_server.get("rest_port")
    app.config["VERSION"] = app.config_server.get("rest_version")
    app.config["MAX_CONTENT_LENGTH"] = filesize_bytes(
        app.config_server.get("rest_max_content_length")
    )
    app.config["PREFIX"] = config.conf["Indexing"].get("index_prefix")
    app.config["REST_URI"] = app.config_server.get("rest_uri")
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

    def __init__(self, app, options_exception_msg):
        self.app = app
        self.options_exception_msg = options_exception_msg

    def options(self):
        try:
            response = _build_cors_preflight_response()
        except Exception:
            self.app.logger.exception(self.options_exception_msg)
            abort(400, message=self.options_exception_msg)
        response.status_code = 200
        return response


class GraphQL(Resource, CorsOptionsRequest):
    """GraphQL API for post request via server."""

    def __init__(self, app, api):
        CorsOptionsRequest.__init__(
            self, app, "Bad options request for the GraphQL query"
        )
        self.api = api

    def post(self):
        logger = self.app.logger
        gql = self.app.config_graphql
        graphQL = f"http://{gql.get('host')}:{gql.get('port')}"
        json_data = request.get_json(silent=True)

        if not json_data:
            logger.warning("GraphQL: Invalid json object {}", request.url)
            abort(400, message="GraphQL: Invalid json object in request")

        try:
            # query GraphQL
            gql_response = requests.post(graphQL, json=json_data)
            gql_response.raise_for_status()
        except requests.exceptions.ConnectionError:
            logger.exception("Connection refused during the GraphQL post request")
            abort(502, message="Network problem, could not post to GraphQL Endpoint")
        except requests.exceptions.Timeout:
            logger.exception("Connection timed out during the GraphQL post request")
            abort(
                504, message="Connection timed out, could not post to GraphQL Endpoint"
            )
        except Exception:
            logger.exception("Exception occurred during the GraphQL post request")
            abort(500, message="INTERNAL ERROR")

        try:
            # construct response object
            raw_response = make_response(gql_response.text)
            response = _corsify_actual_response(raw_response)
        except Exception:
            logger.exception("Exception occurred in GraphQL response construction")
            abort(
                500, message="INTERNAL ERROR",
            )

        response.status_code = gql_response.status_code
        return response


class Elasticsearch(Resource, CorsOptionsRequest):
    """Elasticsearch API for post request via server."""

    def __init__(self, app, api):
        CorsOptionsRequest.__init__(
            self, app, "Bad options request for the Elasticsearch query"
        )
        self.api = api

    def post(self):
        logger = self.app.logger
        es = self.app.config_elasticsearch
        elasticsearch = f"http://{es.get('host')}:{es.get('port')}"
        json_data = request.get_json(silent=True)
        if not json_data:
            logger.warning("Elasticsearch: Invalid json object. Query: {}", request.url)
            abort(400, message="Elasticsearch: Invalid json object in request")

        if not json_data["indices"]:
            logger.warning("Elasticsearch: Missing indices path in the post request")
            abort(400, message="Missing indices path in the Elasticsearch request")

        try:
            # query Elasticsearch
            if "params" in json_data:
                url = f"{elasticsearch}/{json_data['indices']}?{json_data['params']}"
            else:
                url = f"{elasticsearch}/{json_data['indices']}"

            if "payload" in json_data:
                es_response = requests.post(url, json=json_data["payload"])
            else:
                logger.debug("No payload found in Elasticsearch post request json data")
                es_response = requests.get(url)
            es_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.exception("HTTP error {} from Elasticsearch post request", e)
            abort(es_response.status_code, message=f"HTTP error {e} from Elasticsearch")
        except requests.exceptions.ConnectionError:
            logger.exception("Connection refused during the Elasticsearch post request")
            abort(
                502, message="Network problem, could not post to Elasticsearch Endpoint"
            )
        except requests.exceptions.Timeout:
            logger.exception(
                "Connection timed out during the Elasticsearch post request"
            )
            abort(
                504,
                message="Connection timed out, could not post to Elasticsearch Endpoint",
            )
        except Exception:
            logger.exception("Exception occurred during the Elasticsearch post request")
            abort(
                500, message="INTERNAL ERROR",
            )

        try:
            # Construct our response object
            raw_response = make_response(es_response.text)
            response = _corsify_actual_response(raw_response)
        except Exception:
            logger.exception("Exception occurred Elasticsearch response construction")
            abort(
                500, message="INTERNAL ERROR",
            )

        response.status_code = es_response.status_code
        return response


class HostInfo(Resource):
    def __init__(self, app, api):
        self.app = app
        self.api = api

    def get(self):
        try:
            cfg = self.app.config_server
            response = jsonify(
                dict(
                    message=f"{cfg.get('user')}@{cfg.get('host')}"
                    f":{cfg.get('pbench-receive-dir-prefix')}-002"
                )
            )
        except Exception as e:
            self.app.logger.exception(
                "There was something wrong constructing the host info: {}", e
            )
            abort(500, message="There was something wrong with your request")
        response.status_code = 200
        return response


class Upload(Resource):
    def __init__(self, app, api):
        self.app = app
        self.api = api

    def put(self, controller):
        logger = self.app.logger
        if not request.headers.get("filename"):
            logger.debug(
                "Tarfile upload: Post operation failed due to missing filename header"
            )
            abort(
                400,
                message="Missing filename header, POST operation requires a filename header to name the uploaded file",
            )
        filename = secure_filename(request.headers.get("filename"))

        if not request.headers.get("Content-MD5"):
            logger.debug(
                f"Tarfile upload: Post operation failed due to missing md5sum header for file {filename}"
            )
            abort(
                400,
                message="Missing md5sum header, POST operation requires md5sum of an uploaded file in header",
            )
        md5sum = request.headers.get("Content-MD5")

        logger.debug("Receiving file: {}", filename)
        if not allowed_file(filename):
            logger.debug(
                f"Tarfile upload: Bad file extension received for file {filename}"
            )
            abort(400, message="File extension not supported. Only .xz")

        try:
            content_length = int(request.headers.get("Content-Length"))
        except ValueError:
            logger.debug(
                f"Tarfile upload: Invalid content-length header, not an integer for file {filename}"
            )
            abort(400, message="Invalid content-length header, not an integer")
        except Exception:
            logger.debug(
                f"Tarfile upload: No Content-Length header value found for file {filename}"
            )
            abort(400, message="Missing required content-length header")
        else:
            max_len = self.app.config["MAX_CONTENT_LENGTH"]
            if content_length > max_len:
                logger.debug(
                    f"Tarfile upload: Content-Length exceeded maximum upload size allowed. File: {filename}"
                )
                abort(
                    400,
                    message=f"Payload body too large, {content_length:d} bytes, maximum size should be less than "
                    f"or equal to {humanize.naturalsize(max_len)}",
                )
            elif content_length == 0:
                logger.debug(
                    f"Tarfile upload: Content-Length header value is 0 for file {filename}"
                )
                abort(
                    400,
                    message="Upload failed, Content-Length received in header is 0",
                )

        path = Path(self.app.upload_directory, controller)
        path.mkdir(exist_ok=True)
        tar_full_path = Path(path, filename)
        md5_full_path = Path(path, f"{filename}.md5")
        bytes_received = 0

        with tempfile.NamedTemporaryFile(mode="wb", dir=path) as ofp:
            chunk_size = 4096
            logger.debug("Writing chunks")
            hash_md5 = hashlib.md5()

            try:
                while True:
                    chunk = request.stream.read(chunk_size)
                    bytes_received += len(chunk)
                    if len(chunk) == 0 or bytes_received > content_length:
                        break

                    ofp.write(chunk)
                    hash_md5.update(chunk)
            except Exception:
                logger.exception(
                    "Tarfile upload: There was something wrong uploading {}", filename
                )
                abort(500, message=f"There was something wrong uploading {filename}")

            if bytes_received != content_length:
                logger.debug(
                    f"Tarfile upload: Bytes received does not match with content length header value for file {filename}"
                )
                message = (
                    f"Bytes received ({bytes_received}) does not match with content length header"
                    f" ({content_length}), upload failed"
                )
                abort(400, message=message)

            elif hash_md5.hexdigest() != md5sum:
                logger.debug(f"Tarfile upload: md5sum check failed for file {filename}")
                message = f"md5sum check failed for {filename}, upload failed"
                abort(400, message=message)

            # First write the .md5
            try:
                with md5_full_path.open("w") as md5fp:
                    md5fp.write(f"{md5sum} {filename}\n")
            except Exception:
                try:
                    os.remove(md5_full_path)
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    logger.warning(
                        "Failed to remove .md5 {} when trying to clean up: {}}",
                        md5_full_path,
                        exc,
                    )
                logger.exception("Failed to write .md5 file, '{}'", md5_full_path)
                raise

            # Then create the final filename link to the temporary file.
            try:
                os.link(ofp.name, tar_full_path)
            except Exception:
                try:
                    os.remove(md5_full_path)
                except Exception as exc:
                    logger.warning(
                        "Failed to remove .md5 {} when trying to clean up: {}",
                        md5_full_path,
                        exc,
                    )
                logger.exception(
                    "Failed to rename tar ball '{}' to '{}'", ofp.name, md5_full_path,
                )
                raise

        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = 201
        return response
