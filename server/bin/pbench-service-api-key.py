#!/usr/bin/env python3
# -*- mode: python -*-

"""Create an imaginary service account with a single API key.

Create a User record and a matching API key in the database, which can be used
as a service account. The API key provides authentication for services and the
User record allows for ID to name translation.

The primary purpose is to serve as a "legacy" collector for the 0.69-11
passthrough server, but it could also be used for other API clients which don't
require a specific SSO user identity.
"""

from argparse import ArgumentParser
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import uuid

import jwt

from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.database.models.api_keys import APIKey
from pbench.server.database.models.users import User


def main(options, name):
    """Create a Pbench Server service account"""
    config = PbenchServerConfig.create(options.cfg_name)
    logger = get_pbench_logger(name, config)
    init_db(config, logger)

    username = options.username

    # You can specify a nonsense string or let the code generate a real (and
    # "very likely unique") UUID.
    id = options.identity if options.identity else str(uuid.uuid1())

    if User.query(id=id):
        print(f"The user ID {id!r} already exists", file=sys.stderr)
        return 1
    if User.query(username=username):
        print(f"The username {username!r} already exists", file=sys.stderr)
        return 1

    # Create a user proxy object, but don't add it to the session yet.
    user = User(id=id, username=username)

    # NOTE: this needs to closely mimic ApiKey.generate_api_key, however we
    # can't call that here as it depends on a Flask app context. Luckily, the
    # borrowed code is straightforward and relatively small.
    secret = config.get("flask-app", "secret-key")
    payload = {
        "iat": datetime.now(timezone.utc),
        "user_id": user.id,
        "username": user.username,
    }
    try:
        api_key = jwt.encode(payload, secret, algorithm="HS256")
        key = APIKey(key=api_key, user=user, label=options.label)
    except Exception as e:
        print(f"Problem generating API key: {str(e)!r}", file=sys.stderr)
        return 1

    # Add both new rows to the session and commit them.
    try:
        user.add()
        key.add()
    except Exception as e:
        print(f"Problem storing API key: {str(e)!r}", file=sys.stderr)
        return 1

    print(f"Service account {user.username} created, API Key is\n{key.key}")
    return 0


###########################################################################
# Options handling
if __name__ == "__main__":
    run_name = Path(sys.argv[0]).name
    run_name = run_name if run_name[-3:] != ".py" else run_name[:-3]
    parser = ArgumentParser(f"Usage: {run_name} [--config <path-to-config-file>]")
    parser.add_argument(
        "-C",
        "--config",
        dest="cfg_name",
        default=os.environ.get(
            "_PBENCH_SERVER_CONFIG", "/opt/pbench-server/lib/config/pbench-server.cfg"
        ),
        help="Specify config file",
    )
    parser.add_argument(
        "-i",
        "--identity",
        required=False,
        dest="identity",
        help="The UUID identity of the service account",
    )
    parser.add_argument(
        "-l", "--label", required=False, dest="label", help="An API key label"
    )
    parser.add_argument(
        "username",
        help="The username of the service account",
    )
    parsed = parser.parse_args()
    try:
        status = main(parsed, run_name)
    except Exception as e:
        status = 1
        print(f"Unexpected error {e}", file=sys.stderr)
    sys.exit(status)
