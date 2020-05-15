import os
import sys
import hashlib

from pathlib import Path
from flask import request, jsonify, Flask
from flask_restful import Resource, abort, Api
from werkzeug.utils import secure_filename

from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.common.exceptions import BadConfig

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

    try:
        config = PbenchServerConfig(cfg_name)
    except BadConfig as e:
        print(f"{__name__}: {e} (config file {cfg_name})", file=sys.stderr)
        sys.exit(1)

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

    register_endpoints(api, app)

    return app


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
