"""Alembic Migration Driver

This file was auto generated by `alembic init alembic` but was manually altered
to suit the needs of the Pbench server. Re-running `alembic init alembic` will
overwrite these changes!

This Python script runs whenever the alembic migration tool is invoked in
/opt/pbench-server/lib/server/database; it contains instructions to configure
and generate a SQLAlchemy engine, procure a connection from that engine along
with a transaction, and then invoke the migration engine, using the connection
as a source of database connectivity.

This requires access to Pbench library modules and the Pbench server config file
and thus must be run with

    export PYTHONPATH=/opt/pbench-server/lib:${PYTHONPATH}
    export _PBENCH_SERVER_CONFIG=/opt/pbench-server/lib/config/pbench-server.cfg

Examples:

   alembic upgrade head     # upgrade database to the latest
   alembic downgrade base   # downgrade to the original tracked state
"""
import logging
import sys

from alembic import context
from sqlalchemy import create_engine

from pbench.server.api import get_server_config
from pbench.server.database.database import Database

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Add syslog handler to send logs to journald
log = logging.getLogger("alembic")
handler = logging.handlers.SysLogHandler("/dev/log")
log.addHandler(handler)

# add your model's MetaData object here for 'autogenerate' support:

target_metadata = Database.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

try:
    server_config = get_server_config()
    url = Database.get_engine_uri(server_config)
except Exception as e:
    print(e)
    sys.exit(1)


def run_migrations_offline(url: str):
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well.  By skipping the Engine creation we don't
    even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online(url: str):
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection with
    the context.
    """

    connectable = create_engine(url)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    print("running migration offline")
    run_migrations_offline(url)
else:
    print("running migration online")
    run_migrations_online(url)
