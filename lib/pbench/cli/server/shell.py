#!/bin/env python3

from pbench.server.api import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=app.config["PORT"])
