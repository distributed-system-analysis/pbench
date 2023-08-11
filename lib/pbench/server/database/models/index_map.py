import copy
from typing import NewType, Optional

from sqlalchemy import Column, ForeignKey, Integer, JSON, String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import relationship

from pbench.server import JSONOBJECT
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset


class IndexMapError(Exception):
    """
    This is a base class for errors reported by the IndexMap class. It is
    never raised directly, but may be used in "except" clauses.
    """

    pass


class IndexMapSqlError(IndexMapError):
    """SQLAlchemy errors reported through IndexMap operations.

    The exception will identify the base name of the Elasticsearch index,
    along with the operation being attempted; the __cause__ will specify the
    original SQLAlchemy exception.
    """

    def __init__(self, operation: str, dataset: Dataset, name: str, cause: str):
        self.operation = operation
        self.dataset = dataset.name if dataset else "unknown"
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Error {self.operation} index {self.dataset}:{self.name}: {self.cause}"


class IndexMapNotFound(IndexMapError):
    """Attempt to find a IndexMap that doesn't exist."""

    def __init__(self, dataset: Dataset, name: str):
        self.dataset = dataset.name
        self.name = name

    def __str__(self) -> str:
        return f"Dataset {self.dataset!r} index {self.name!r} not found"


class IndexMapDuplicate(IndexMapError):
    """Attempt to commit a duplicate IndexMap id."""

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Duplicate template {self.name!r}: {self.cause}"


class IndexMapMissingParameter(IndexMapError):
    """Attempt to commit a IndexMap with missing parameters."""

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Missing required parameters in {self.name!r}: {self.cause}"


IndexMapType = NewType("IndexMapType", dict[str, dict[str, list[str]]])


class IndexMap(Database.Base):
    """
    A Pbench Elasticsearch index map. This records all of the versioned indices
    occupied by documents from a dataset, and the document IDs in each index.

    Columns:
        id          Generated unique ID of table row
        dataset     Reference to the associated dataset
        index       Elasticsearch full index name
        documents   JSON list of document IDs
    """

    __tablename__ = "indexmaps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_ref = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    root = Column(String(255), index=True, nullable=False)
    index = Column(String(255), index=True, nullable=False)
    documents = Column(JSON, nullable=False)
    dataset = relationship("Dataset")

    @classmethod
    def create(cls, dataset: Dataset, map: IndexMapType):
        """
        A simple factory method to construct a set of new index rows from a
        JSON document.

        The source JSON document has a nested structure such as

        {
            {"r1": {"i1": ["d1", "d2", ...], "i2": ["d3", "d4", ...]}},
            {"r2": {"ir1": ["dr1", "dr2", ...], "ir2": ["dr3", "dr4", ...]}},
        }

        We usually iterate through all document IDs for a particular root
        index name, so we break down the JSON to store a document ID list for
        each index in a separate row.

        Args:
            dataset: the Dataset object
            map: a JSON index map
        """
        instances = []
        for root, indices in map.items():
            for index, docs in indices.items():
                m = IndexMap(dataset=dataset, root=root, index=index, documents=docs)
                instances.append(m)

        try:
            Database.db_session.add_all(instances)
        except Exception as e:
            raise IndexMapSqlError("add_all", dataset, "all", e)

        cls.commit(dataset, "create")

    @classmethod
    def merge(cls, dataset: Dataset, merge_map: IndexMapType):
        """Merge two index maps, generated by distinct phases of indexing.

        Generally the root and index names won't overlap, but we allow for that
        just in case.

        We expect to update the database and SQLAlchemy's change detection is
        shallow: to be safe, we start with a deep copy of the current map.

        Args:
            merge_map: an index map to merge into the indexer map attribute
        """

        try:
            indices = (
                Database.db_session.query(IndexMap)
                .filter(IndexMap.dataset == dataset)
                .all()
            )
        except SQLAlchemyError as e:
            raise IndexMapSqlError("finding", dataset, "all", str(e))

        if indices is None:
            raise IndexMapNotFound(dataset, "all")

        old_roots = set(i.root for i in indices)
        new_roots = set(merge_map.keys())

        # Any new roots can just be added to the table
        for r in new_roots - old_roots:
            for i, d in merge_map[r].items():
                Database.db_session.add(
                    IndexMap(dataset=dataset, root=r, index=i, documents=d)
                )

        # Roots in both need to be merged
        for r in old_roots & new_roots:
            old_indices = set(i.index for i in indices if i.root == r)
            new_indices = set(merge_map[r].keys())

            # New indices can be added to the table
            for i in new_indices - old_indices:
                Database.db_session.add(
                    IndexMap(
                        dataset=dataset, root=r, index=i, documents=merge_map[r][i]
                    )
                )

            # Indices in both need to merge the document ID lists
            for i in old_indices & new_indices:
                for index in indices:
                    if index.index == i:
                        x = copy.deepcopy(index.documents)
                        x.extend(merge_map[r][i])
                        index.documents = x

        cls.commit(dataset, "merge")

    @staticmethod
    def find(dataset: Dataset, index: str) -> Optional[JSONOBJECT]:
        """
        Return the indices matching the specified root index name. For
        example, find(dataset, "run-data").

        Args:
            dataset: Dataset object
            index: Root index name

        Raises:
            IndexMapSqlError: problem interacting with Database

        Returns:
            A JSON object with a list of document IDs for each index associated
            with the specified dataset and root index name.
        """
        try:
            map = (
                Database.db_session.query(IndexMap)
                .filter(IndexMap.dataset == dataset, IndexMap.root == index)
                .all()
            )
        except SQLAlchemyError as e:
            raise IndexMapSqlError("finding", dataset, index, str(e))

        return {i.index: i.documents for i in map}

    @staticmethod
    def map(dataset: Dataset) -> IndexMapType:
        """
        Return a JSON object with a document list for each index associated
        with the dataset.

        Args:
            dataset: Dataset object

        Raises:
            IndexMapSqlError: problem interacting with Database
            IndexMapNotFound: the specified template doesn't exist

        Returns:
            A two-level dict with document IDs listed under each index name
            categorized under root index names.
        """
        try:
            indices = (
                Database.db_session.query(IndexMap)
                .filter(IndexMap.dataset == dataset)
                .all()
            )
        except SQLAlchemyError as e:
            raise IndexMapSqlError("map", dataset, "all", str(e))

        if indices is None:
            raise IndexMapNotFound(dataset, "all")

        map: IndexMapType = {}
        for m in indices:
            try:
                r = map[m.root]
                try:
                    r[m.index].extend(m.documents)
                except KeyError:
                    r[m.index] = m.documents
            except KeyError:
                sub = {m.index: m.documents}
                map[m.root] = sub
        return map

    def __str__(self) -> str:
        """
        Return a string representation of the map object

        Returns:
            string: Representation of the template
        """
        return (
            f"{self.dataset.name} [{self.root}:{self.index}]: {len(self.documents)} IDs"
        )

    @staticmethod
    def _decode(index: str, exception: IntegrityError) -> Exception:
        """
        Decode a SQLAlchemy IntegrityError to look for a recognizable UNIQUE
        or NOT NULL constraint violation. Return the original exception if
        it doesn't match.

        Args:
            index: The index name
            exception: An IntegrityError to decode

        Returns:
            a more specific exception, or the original if decoding fails
        """
        # Postgres engine returns (code, message) but sqlite3 engine only
        # returns (message); so always take the last element.
        cause = exception.orig.args[-1]
        if cause.find("UNIQUE constraint") != -1:
            return IndexMapDuplicate(index, cause)
        elif cause.find("NOT NULL constraint") != -1:
            return IndexMapMissingParameter(index, cause)
        return exception

    @classmethod
    def commit(cls, dataset: Dataset, operation: str):
        """Commit changes to the database."""
        try:
            Database.db_session.commit()
        except IntegrityError as e:
            Database.db_session.rollback()
            raise cls._decode("any", e)
        except Exception as e:
            Database.db_session.rollback()
            raise IndexMapSqlError(operation, dataset, "any", str(e))
