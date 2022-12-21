"""
For any new database model added in the models directory
an import statement of the same is required here.
"""
from pbench.server.database.database import Database
from pbench.server.database.models.active_token import ActiveToken  # noqa F401
from pbench.server.database.models.audit import Audit  # noqa F401
from pbench.server.database.models.dataset import Dataset  # noqa F401
from pbench.server.database.models.dataset import Metadata  # noqa F401
from pbench.server.database.models.server_config import ServerConfig  # noqa F401
from pbench.server.database.models.template import Template  # noqa F401
from pbench.server.database.models.user import User  # noqa F401


def init_db():
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
    Database.init_db()
