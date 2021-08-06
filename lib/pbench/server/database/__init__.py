"""
For any new database model added in the models directory
an import statement of the same is required here.
"""
from pbench.server.database.models.active_tokens import ActiveTokens  # noqa F401
from pbench.server.database.models.users import User  # noqa F401
from pbench.server.database.models.datasets import Dataset, Metadata  # noqa F401
from pbench.server.database.models.template import Template  # noqa F401

from pbench.server.database.database import Database


def init_db(server_config, logger):
    """
    Utility method for initializing the database.

    In order to register all the tables properly in our database, the db models
    need to be imported before the call to the Database.init_db() function.

    A lot of independent functionality in our code depends on database
    access without creating the flask app.  Invoking init_db() from here
    makes sure all models are imported properly; therefore, all of the code
    where we need standalone db access should invoke this function instead
    of directly invoking Database.init_db().
    """
    Database.init_db(server_config=server_config, logger=logger)
