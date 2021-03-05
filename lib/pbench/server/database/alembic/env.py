"""
This file is auto generated when we run `alembic init alembic` but modified according to our needs.
This Python script runs whenever the alembic migration tool is invoked.
It contains instructions to configure and generate a SQLAlchemy engine,
procure a connection from that engine along with a transaction, and then
invoke the migration engine, using the connection as a source of database connectivity.
"""
import sys
import logging
from logging.config import fileConfig

from alembic import context

from pbench.server.database.database import Database
from pbench.common.logger import get_pbench_logger
from pbench.server.api import get_server_config

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

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


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    try:
        server_config = get_server_config()
        logger = get_pbench_logger(__name__, server_config)
    except Exception as e:
        print(e)
        sys.exit(1)

    url = Database.get_engine_uri(server_config, logger)
    if url is None:
        sys.exit(1)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    try:
        server_config = get_server_config()
        logger = get_pbench_logger(__name__, server_config)
    except Exception as e:
        print(e)
        sys.exit(1)

    connectable = Database.init_engine(server_config, logger)
    # connectable = engine_from_config(
    #     config.get_section(config.config_ini_section),
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    print("running migration offline")
    run_migrations_offline()
else:
    print("running migration online")
    run_migrations_online()
