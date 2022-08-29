from enum import auto, Enum
from logging import Logger
from typing import List, Optional

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
        return f"<Synchronizer for component {self.component!r}"

    def next(self, operation: Operation) -> List[Dataset]:
        """
        This is a very specialized query to return a list of datasets with
        specific associated metadata, specifically containing a known
        "OPERATION" enum value in the 'server.operation' metadata field.

        NOTE:

        This can be considered a prototype for a general "query by metadata"
        mechanism (PBENCH-825), however I haven't attempted to work out a full
        generalization. At this point I'm happen enough to have a relatively
        simple special purpose query; but it bring hope that the general query
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
            query = (
                query.filter(Metadata.key == Metadata.SERVER)
                .filter(Metadata.value["operation"].as_string() == operation.name)
                .order_by(Dataset.name)
            )
            self.logger.info(
                "QUERY {}",
                query.statement.compile(compile_kwargs={"literal_binds": True}),
            )
            return list(query.all())
        except Exception as e:
            self.logger.exception("Failed to query for {}", operation)
            raise SyncSqlError("next") from e

    def update(
        self,
        dataset: Dataset,
        did: Optional[Operation] = None,
        enabled: Optional[List[Operation]] = None,
    ):
        """
        Advertise the operations for which the dataset is now ready.

        Args:
            dataset: The dataset
            did: The operation (if any) just completed, which will marked done
            enabled: A list (if any) of operations for which the dataset is now
                eligible.
        """
        with Database.db_session.begin_nested():
            # Put the `getvalue` inside a transaction with the `setvalue` to
            # approximate an atomic update.
            operations: List[str] = Metadata.getvalue(dataset, Metadata.OPERATION)

            print(f"OLD operations {operations}")

            if type(operations) is str:
                # FIXME: compatibility hack for hacking
                operations = [operations]
            elif not operations:
                operations = []

            if did:
                try:
                    operations.remove(did.name)
                except ValueError:
                    pass

            if enabled:
                operations.extend([o.name for o in enabled if o.name not in operations])

            print(f"DID {did}, DOING {operations}")

            Metadata.setvalue(dataset, Metadata.OPERATION, operations)
            Database.db_session.commit()

    def error(self, dataset: Dataset, message: str):
        """
        Record an error in the component for which the Sync object was created.

        Args:
            dataset: The dataset affected
            message: A message to be stored at "server.errors.{component}"
        """
        self.logger.error("Error in {} for {}: {}", self.component, dataset, message)
        Metadata.setvalue(dataset, f"server.errors.{self.component}", message)
