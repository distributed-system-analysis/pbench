from pbench.server.database.models import *  # noqa
from pbench.server.database.database import Database


def init_db(server_config, logger):
    """
    Utility method for initializing the database.

    In order to register all the tables properly in our database, db models need to be imported before the
    call to Database.init function.

    Lot of independant functionality in our code depends on database access without creating the flask app.
    Invoking init_db from here make sure all models are imported properly, all the functionalities where we
    need a standalone db access should invoke this function instead of directly invoking Database.init_db
    """
    Database.init_db(server_config=server_config, logger=logger)
