"""
For any new database model added in the models directory
an import statemnt of the same is required here.
"""
from pbench.server.database.models.active_tokens import ActiveTokens  # noqa
from pbench.server.database.models.users import User  # noqa
from pbench.server.database.models.tracker import Dataset, Metadata  # noqa
