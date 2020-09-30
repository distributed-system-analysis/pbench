#!/bin/env python3

from pbench.server.api import create_app
import subprocess


def main():
    app = create_app()
    port = app.config["PORT"]
    host = app.config["BIND_HOST"]
    workers = app.config["WORKERS"]
    subprocess.run(
        [
            "gunicorn",
            "--workers",
            str(workers),
            "--pid",
            "/run/pbench-server/gunicorn.pid",
            "--bind",
            f"{str(host)}:{str(port)}",
            "pbench.server.api:create_app()",
        ]
    )
