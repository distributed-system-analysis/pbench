#!/bin/env python3

from pbench.server.api import create_app


def main():
    app = create_app()
    app.run(debug=True, port=app.config["PORT"])
