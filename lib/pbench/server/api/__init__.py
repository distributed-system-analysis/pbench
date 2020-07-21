import os
import sys
import hashlib
import requests

from pathlib import Path
from flask import request, jsonify, Flask, make_response
from flask_restful import Resource, abort, Api
from werkzeug.utils import secure_filename

from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig

ALLOWED_EXTENSIONS = {"xz"}

app = None


def allowed_file(filename):
    try:
        fn = filename.rsplit(".", 1)[1].lower()
    except IndexError:
        return False
    allowed = "." in filename and fn in ALLOWED_EXTENSIONS
    return allowed


def register_endpoints(api, app):
    api.add_resource(Upload, f"{app.config['REST_URI']}/upload")
    api.add_resource(HostInfo, f"{app.config['REST_URI']}/host_info")
    api.add_resource(Download, f"{app.config['REST_URI']}/download")


def create_app():
    global app

    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        print(
            f"{__name__}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG",
            file=sys.stderr,
        )
        sys.exit(1)

    config = PbenchServerConfig(cfg_name)

    app = Flask(__name__)
    api = Api(app)

    app.logger = get_pbench_logger(__name__, config)

    app.config_server = config.conf["pbench-server"]

    prdp = app.config_server.get("pbench-receive-dir-prefix")
    try:
        upload_directory = Path(f"{prdp}-002").resolve(strict=True)
    except Exception:
        app.logger.error("Missing config variable for pbench-receive-dir-prefix")
        sys.exit(1)
    else:
        app.upload_directory = upload_directory

    app.config["PORT"] = app.config_server.get("rest_port")
    app.config["VERSION"] = app.config_server.get("rest_version")
    app.config["MAX_CONTENT_LENGTH"] = app.config_server.get("rest_max_content_length")
    app.config["REST_URI"] = app.config_server.get("rest_uri")
    app.config["LOG"] = app.config_server.get("rest_log")

    app.logger = get_pbench_logger(__name__, app.config_pbench)

    register_endpoints(api, app)

    return app


def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response


def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


class Download(Resource):
    def post(self):
        global app
        try:
            # query ElasticSearch
            json_data = request.get_json()
            print("payload" in json_data)
            print(json_data)
            print("url" in json_data)
            print(json_data["url"])
            if "payload" in json_data:
                response = requests.post(json_data["url"], json=json_data["payload"])
            else:
                response = requests.get(json_data["url"])

            # construct response object
            response = make_response(response.text)
            response = _corsify_actual_response(response)
        except Exception:
            app.logger.debug("There was something wrong with the POST request.")
            abort(400, message="There was something wrong with your download request")
        return response

    # From the client side, an OPTIONS request is initiated before every POST to request CORS.
    # On the server side, the server must specify the response headers to grant CORS accordingly.

    def options(self):
        try:
            response = _build_cors_preflight_response()
        except Exception:
            app.logger.debug("There was something wrong with the OPTIONS request.")
            abort(400, message="There was something wrong with your request")
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
            app.logger.exception(
                "There was something wrong constructing the host info."
            )
            abort(500, message="There was something wrong with your request")
        response.status_code = 200
        return response


class Upload(Resource):
    def post(self):
        global app
        if not request.headers.get("filename"):
            app.logger.debug("Missed filename in header")
            abort(400, message="Missing filename header in request")
        filename = secure_filename(request.headers.get("filename"))

        if not request.headers.get("md5sum"):
            app.logger.debug("Missed md5sum in header")
            abort(400, message="Missing md5sum header in request")
        md5sum = request.headers.get("md5sum")

        app.logger.debug("Receiving file: {}", filename)
        if not allowed_file(filename):
            app.logger.debug("Bad file extension received")
            abort(400, message="File extension not supported. Only .xz")

        full_path = app.upload_directory / filename

        try:
            with open(full_path, "wb") as f:
                chunk_size = 4096
                app.logger.debug("Writing chunks")
                hash_md5 = hashlib.md5()

                while True:
                    chunk = request.stream.read(chunk_size)
                    if len(chunk) == 0:
                        break

                    f.write(chunk)
                    hash_md5.update(chunk)
        except Exception:
            app.logger.exception("There was something wrong uploading {}", filename)
            abort(500, message=f"There was something wrong uploading {filename}")

        if hash_md5.hexdigest() != md5sum:
            abort(400, message=f"md5sum check failed for {filename}")

        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = 201
        return response
