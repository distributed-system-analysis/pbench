from typing import NewType, Optional

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import relationship

from pbench.server.database.database import Database
from pbench.server.database.models import decode_sql_error
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
    along with the operation being attempted.
    """

    def __init__(self, cause: Exception, **kwargs):
        super().__init__(
            f"Index SQL error on {kwargs.get('operation')} "
            f"{kwargs.get('dataset')}:{kwargs.get('name')}: '{cause}'"
        )
        self.cause = cause
        self.kwargs = kwargs


class IndexMapDuplicate(IndexMapError):
    """Attempt to commit a duplicate IndexMap id."""

    def __init__(self, cause: Exception, **kwargs):
        super().__init__(f"Duplicate index map {kwargs.get('name')!r}: '{cause}'")
        self.cause = cause
        self.kwargs = kwargs


class IndexMapMissingParameter(IndexMapError):
    """Attempt to commit a IndexMap with missing parameters."""

    def __init__(self, cause: Exception, **kwargs):
        super().__init__(
            f"Missing required parameters in {kwargs.get('name')!r}: '{cause}'"
        )
        self.cause = cause
        self.kwargs = kwargs


IndexMapType = NewType("IndexMapType", dict[str, list[str]])


class IndexMap(Database.Base):
    """
    A Pbench Elasticsearch index map. This records all of the versioned indices
    occupied by documents from a dataset, and the document IDs in each index.

    Columns:
        id          Generated unique ID of table row
        dataset     Reference to the associated dataset
        index       Elasticsearch full index name
    """

    __tablename__ = "indexmaps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_ref = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    root = Column(String(255), index=True, nullable=False)
    index = Column(String(255), index=True, nullable=False)
    dataset = relationship("Dataset")

    @classmethod
    def create(cls, dataset: Dataset, map: IndexMapType):
        """
        A simple factory method to construct a set of new index rows from a
        JSON document.

        The source JSON document has a nested structure associating a set of
        "root index" names (such as "run-toc") with a list of fully qualified
        index names (with prefix and timeseries date suffix) such as
        "prefix.run-toc.2023-07".

        {
            "root-a": ["index-a.1", "index-a.2"],
            "root-b": ["index-b.1", "index-b.2"]
        }

        Args:
            dataset: the Dataset object
            map: a JSON index map
        """
        instances = []
        for root, indices in map.items():
            for index in indices:
                m = IndexMap(dataset=dataset, root=root, index=index)
                instances.append(m)

        try:
            Database.db_session.add_all(instances)
        except Exception as e:
            raise IndexMapSqlError(e, operation="create", dataset=dataset, name="all")

        cls.commit(dataset, "create")

    @classmethod
    def delete(cls, dataset: Dataset, root: Optional[str] = None):
        """Delete the indices matching the specified root index name.

        Args:
            dataset: Dataset object
            root: Root index name

        Raises:
            IndexMapSqlError: problem interacting with Database
        """
        filters = [IndexMap.dataset == dataset]
        if root:
            filters.append(IndexMap.root == root)
        try:
            Database.db_session.query(IndexMap).filter(*filters).delete()
            cls.commit(dataset, "delete")
        except SQLAlchemyError as e:
            raise IndexMapSqlError(e, operation="delete", dataset=dataset, name=root)

    @classmethod
    def merge(cls, dataset: Dataset, merge_map: IndexMapType):
        """Merge two index maps, generated by distinct phases of indexing.

        Generally the root and index names won't overlap, but we allow for that
        just in case.

        Args:
            merge_map: an index map to merge into the indexer map attribute
        """

        try:
            indices = (
                Database.db_session.query(IndexMap)
                .filter(IndexMap.dataset == dataset)
                .all()
            )

            # Cross reference the list of IndexMap entries by root and full
            # index name in a structure similar to IndexMapType. (But the
            # leaf nodes point back to the DB model objects to allow updating
            # them.) Note that we allow for a list of IndexMap model objects
            # for each fully qualified index name although in theory that
            # shouldn't happen.
            map: dict[str, dict[str, list[IndexMap]]] = {}
            for i in indices:
                if i.root in map.keys():
                    if i.index in map[i.root]:
                        map[i.root][i.index].append(i)
                    else:
                        map[i.root][i.index] = [i]
                else:
                    map[i.root] = {i.index: [i]}

            old_roots = set(map.keys())
            new_roots = set(merge_map.keys())

            # Any new roots can just be added to the table
            for r in new_roots - old_roots:
                for i in merge_map[r]:
                    Database.db_session.add(IndexMap(dataset=dataset, root=r, index=i))

            # Roots in both need to be merged
            for r in old_roots & new_roots:
                old_indices = set(map[r])
                new_indices = set(merge_map[r])

                # New indices can be added to the table: indices that already
                # exist don't need to be added, and can be ignored.
                for i in new_indices - old_indices:
                    Database.db_session.add(IndexMap(dataset=dataset, root=r, index=i))
        except SQLAlchemyError as e:
            raise IndexMapSqlError(e, operation="merge", dataset=dataset, name="all")

        cls.commit(dataset, "merge")

    @staticmethod
    def indices(dataset: Dataset, root: Optional[str] = None) -> list[str]:
        """Return the indices matching the specified root index name.

        Args:
            dataset: Dataset object
            root: Root index name

        Raises:
            IndexMapSqlError: problem interacting with Database

        Returns:
            The index names matching the root index name
        """
        filters = [IndexMap.dataset == dataset]
        if root:
            filters.append(IndexMap.root == root)
        try:
            map = Database.db_session.query(IndexMap).filter(*filters).all()
        except SQLAlchemyError as e:
            raise IndexMapSqlError(e, operation="indices", dataset=dataset, name=root)

        return [str(i.index) for i in map]

    @staticmethod
    def exists(dataset: Dataset) -> bool:
        """Determine whether the dataset has at least one map entry.

        Args:
            dataset: Dataset object

        Returns:
            True if the dataset has at least one index map entry
        """

        try:
            c = (
                Database.db_session.query(IndexMap)
                .filter(IndexMap.dataset == dataset)
                .count()
            )
            return bool(c)
        except SQLAlchemyError as e:
            raise IndexMapSqlError(e, operation="exists", dataset=dataset, name="any")

    def __str__(self) -> str:
        """
        Return a string representation of the map object

        Returns:
            string: Representation of the template
        """
        return f"{self.dataset.name} [{self.root}:{self.index}]"

    @classmethod
    def commit(cls, dataset: Dataset, operation: str):
        """Commit changes to the database."""
        try:
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            raise decode_sql_error(
                e,
                on_duplicate=IndexMapDuplicate,
                on_null=IndexMapMissingParameter,
                fallback=IndexMapSqlError,
                operation=operation,
                dataset=dataset,
                name="all",
            ) from e
