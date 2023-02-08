from logging import Logger
import time
from typing import Optional

from sqlalchemy import or_

from pbench.server.database.database import Database
from pbench.server.database.models.datasets import (
    Dataset,
    Operation,
    OperationName,
    OperationState,
)


class SyncError(Exception):
    def __str__(self) -> str:
        return "Component synchronization error"


class SyncSqlError(SyncError):
    def __init__(self, component: OperationName, operation: str):
        self.component = component
        self.operation = operation

    def __str__(self) -> str:
        return f"Sql error executing {self.component.name} {self.operation}"


class Sync:

    RETRIES = 10  # Retry 10 times on commit failure
    DELAY = 0.1  # Wait 1/10 second between retries

    def __init__(self, logger: Logger, component: OperationName):
        self.logger: Logger = logger
        self.component: OperationName = component

    def __str__(self) -> str:
        return f"<Synchronizer for component {self.component.name!r}>"

    def next(self) -> list[Dataset]:
        """
        This is a specialized query to return a list of datasets with the READY
        OperationState for the Sync component.

        NOTE:

        We use our sessionmaker to construct a special session with a context
        manager so that we can begin a local transaction without concern about
        SQLAlchemy's context or whether our casual global session might have a
        transaction already in progress.

        This however presents a small problem in that SQLAlchemy is unhappy
        when proxy objects are used out of scope of the session that spawned
        them. To resolve this in a somewhat hacky but effective way, we're
        transporting only the resource IDs across the barrier and fetching
        new proxy objects using the general session.

        Returns:
            A list of Dataset objects which have an associated
            Operation object in READY state.
        """
        try:
            with Database.maker.begin() as session:
                query = session.query(Dataset).join(Operation)
                query = query.filter(
                    Operation.name == self.component,
                    Operation.state == OperationState.READY,
                )
                query = query.order_by(Dataset.resource_id)
                Database.dump_query(query, self.logger)
                id_list = [d.resource_id for d in query.all()]
            return [Dataset.query(resource_id=i) for i in id_list]
        except Exception as e:
            self.logger.exception("Failed to find 'next' for {}", self.component.name)
            raise SyncSqlError(self.component, "next") from e

    def update(
        self,
        dataset: Dataset,
        state: Optional[OperationState] = None,
        enabled: Optional[list[OperationName]] = None,
        message: Optional[str] = None,
    ):
        """Advertise the operations for which the dataset is now ready.

        Args:
            dataset: The dataset
            state: The new OperationState of the component Operation
            enabled: A list (if any) of operations for which the dataset is now
                eligible.
            message: An optional status message
        """

        if enabled is None:
            enabled = []

        self.logger.debug(
            "Dataset {} did {}, enabling {} with message {!r}",
            dataset.name,
            state.name if state else "nothing",
            [e.name for e in enabled] if enabled else "none",
            message,
        )

        # Don't reference the Dataset (which is outside our session scope)
        # inside the context manager.
        ds_name = dataset.name
        ds_id = dataset.id
        retries = self.RETRIES

        # To avoid SELECT statements after updates, and the whole complication
        # of SQLAlchemy AUTOFLUSH semantics, we're going to gather a set of all
        # the operation rows we might need to update at the beginning.
        match_set: set[OperationName] = set()
        if state or message:
            match_set.add(self.component)
        if enabled:
            match_set.update(enabled)

        filters = [Operation.name == n for n in match_set]

        while retries > 0:
            try:
                with Database.maker.begin() as session:
                    query = session.query(Operation).filter(
                        Operation.dataset_ref == ds_id, or_(*filters)
                    )
                    Database.dump_query(query, self.logger)
                    matches = query.all()
                    ops: dict[OperationName, Operation] = {o.name: o for o in matches}

                    if state or message:
                        op: Operation = ops.get(self.component)
                        if op:
                            if state:
                                op.state = state
                            if message:
                                op.message = message
                        else:
                            op = Operation(
                                dataset_ref=ds_id,
                                name=self.component,
                                state=state if state else OperationState.FAILED,
                                message=message,
                            )
                            session.add(op)

                    for e in enabled:
                        op = ops.get(e)
                        if op:
                            op.state = OperationState.READY
                        else:
                            op = Operation(
                                dataset_ref=ds_id, name=e, state=OperationState.READY
                            )
                            session.add(op)
                return
            except Exception as e:
                self.logger.warning(
                    "{} 'update' {} error ({}): {}",
                    self.component,
                    ds_name,
                    retries,
                    str(e),
                )
                retries -= 1
                if retries <= 0:
                    raise SyncSqlError(self.component, "update") from e
                time.sleep(self.DELAY)

    def error(self, dataset: Dataset, message: str):
        """
        Record an error in the component for which the Sync object was created.

        Args:
            dataset: The dataset affected
            message: A message to be stored at "server.status.{component}"
        """
        self.logger.debug(
            "{} error {}: {}", dataset.resource_id, self.component.name, message
        )

        # Don't reference the Dataset (which is outside our session scope)
        # inside the context manager.
        ds_name = dataset.name
        ds_id = dataset.id
        retries = self.RETRIES
        while retries > 0:
            try:
                with Database.maker.begin() as session:
                    query = session.query(Operation).filter(
                        Operation.name == self.component, Operation.dataset_ref == ds_id
                    )
                    match = query.first()
                    if match:
                        match.state = OperationState.FAILED
                        match.message = message
                    else:
                        row = Operation(
                            dataset_ref=ds_id,
                            name=self.component,
                            state=OperationState.FAILED,
                            message=message,
                        )
                        session.add(row)
                return
            except Exception as e:
                self.logger.warning(
                    "{} {} 'error' ({}) error updating message: {}",
                    self.component.name,
                    ds_name,
                    retries,
                    str(e),
                )
                retries -= 1
                if retries <= 0:
                    raise SyncSqlError(self.component, "update") from e
                time.sleep(self.DELAY)
