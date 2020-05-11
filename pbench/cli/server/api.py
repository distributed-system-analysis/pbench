#!/usr/bin/env python3
import hashlib
import os

from flask import request, jsonify, Flask
from flask_restful import Resource, abort, Api
from werkzeug.utils import secure_filename

from pbench import get_pbench_logger
from pbench.server.api.config import ServerConfig

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

    config = ServerConfig()

    app = Flask(__name__)
    api = Api(app)

    app.config_pbench = config.get_pbench_config()
    app.config_server = config.get_server_config()

    app.config["PORT"] = app.config_server.get("rest_port")
    app.config["VERSION"] = app.config_server.get("rest_version")
    app.config["MAX_CONTENT_LENGTH"] = app.config_server.get("rest_max_content_length")
    app.config["REST_URI"] = app.config_server.get("rest_uri")
    app.config["LOG"] = app.config_server.get("rest_log")

    app.logger = get_pbench_logger(__name__, app.config_pbench)

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
            app.logger.debug("There was something wrong constructing the host info.")
            abort(400, message="There was something wrong with your request")
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

        app.logger.debug(f"Receiving file: {filename}")
        if not allowed_file(filename):
            app.logger.debug("Bad file extension received")
            abort(400, message="File extension not supported. Only .xz")

        upload_directory = app.config_server.get("pbench-receive-dir-prefix")
        if not upload_directory:
            app.logger.debug("Missing config variable for pbench-receive-dir-prefix")
            abort(400, message="Missing config variable for pbench-receive-dir-prefix")
        if not os.path.exists(upload_directory):
            os.mkdir(upload_directory)
        full_path = os.path.join(upload_directory, filename)

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
            abort(400, message=f"There was something wrong uploading {filename}")

        if hash_md5.hexdigest() != md5sum:
            abort(400, message=f"md5sum check failed for {filename}")

        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = 201
        return response


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=app.config["PORT"])
