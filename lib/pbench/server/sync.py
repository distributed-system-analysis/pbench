from enum import auto, Enum
from logging import DEBUG, Logger
from typing import List, Optional

from pbench.server import JSONVALUE
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset, Metadata


class Operation(Enum):
    """
    Define the operations that can be performed on a dataset tarball by the
    various stages of our server pipeline.
    """

    BACKUP = auto()
    DELETE = auto()
    UNPACK = auto()
    COPY_SOS = auto()
    INDEX = auto()
    INDEX_TOOL = auto()
    RE_INDEX = auto()


class SyncError(Exception):
    def __str__(self) -> str:
        return "Component synchronization error"


class SyncSqlError(SyncError):
    def __init__(self, operation: str):
        self.operation = operation

    def __str__(self) -> str:
        return f"Sql error executing {self.operation}"


class Sync:
    def __init__(self, logger: Logger, component: str):
        self.logger = logger
        self.component = component

    def __str__(self) -> str:
        return f"<Synchronizer for component {self.component!r}>"

    def next(self, operation: Operation) -> List[Dataset]:
        """
        This is a very specialized query to return a list of datasets with
        specific associated metadata, specifically containing a known
        "OPERATION" enum value in the 'server.operation' metadata field.

        NOTE:

        This can be considered a prototype for a general "query by metadata"
        mechanism (PBENCH-825), however I haven't attempted to work out a full
        generalization. At this point I'm happy enough to have a relatively
        simple special purpose query; but it gives me hope that a general query
        is achievable.

        Args:
            A desired Operation enum value

        Returns:
            A list of Dataset objects which have an associated
            "server.operation" metadata value containing the name of the
            operation enum.
        """
        try:
            query = Database.db_session.query(Dataset).join(Metadata)
            query = query.filter(Metadata.key == Metadata.SERVER)
            term = Metadata.value["operation"].as_string().contains(operation.name)
            query = query.filter(term)
            query = query.order_by(Dataset.name)
            if self.logger.isEnabledFor(DEBUG):
                q_str = query.statement.compile(compile_kwargs={"literal_binds": True})
                self.logger.debug("QUERY {}", q_str)
            return list(query.all())
        except Exception as e:
            self.logger.exception("Failed to query for {}", operation)
            raise SyncSqlError("next") from e

    def update(
        self,
        dataset: Dataset,
        did: Optional[Operation] = None,
        enabled: Optional[List[Operation]] = None,
        status: Optional[str] = None,
    ):
        """
        Advertise the operations for which the dataset is now ready.

        TODO: It'd be nice to nest this inside a transaction so it's all
        atomic. This seems to be difficult to achieve in a manner that works
        both with PostgreSQL for production and sqlite3 for unit tests. When
        we've removed the use of sqlite3 we can make this a nested transaction.

        Args:
            dataset: The dataset
            did: The operation (if any) just completed, which will be removed
                from the list of eligible operations.
            enabled: A list (if any) of operations for which the dataset is now
                eligible.
            status: A status message (if not specified, and enabling new
                operation(s), the default is "ok")
        """
        ops: JSONVALUE = Metadata.getvalue(dataset, Metadata.OPERATION)
        message = status

        if not ops:
            operations = set()
        else:
            operations = set(ops)
            if did:
                operations.discard(did.name)

        if enabled:
            operations.update(o.name for o in enabled)
            if not message:
                message = "ok"

        try:
            Metadata.setvalue(dataset, Metadata.OPERATION, sorted(operations))
            if message:
                Metadata.setvalue(dataset, "server.status." + self.component, message)
        except Exception as e:
            self.logger.warning("{} error updating ops: {}", dataset.name, str(e))
            raise

    def error(self, dataset: Dataset, message: str):
        """
        Record an error in the component for which the Sync object was created.

        Args:
            dataset: The dataset affected
            message: A message to be stored at "server.status.{component}"
        """
        Metadata.setvalue(dataset, "server.status." + self.component, message)
