"""The SQLAlchemy mock infrastructure here is not completely generalized, but
is currently sufficient to support the ServerConfig and Audit DB unit tests.
"""

from typing import Optional

from sqlalchemy import Column

from pbench.server.database.database import Database


class FakeDBOrig:
    """
    A simple mocked replacement for SQLAlchemy's engine "origin" object in
    exceptions.
    """

    def __init__(self, arg: str):
        """
        Create an 'orig' object

        Args:
            arg:    A text string passing information about the engine's
                    SQL query.
        """
        self.args = [arg]


class FakeRow:
    """
    Maintain an internal "database row" copy that we can use to verify the
    committed records and compare active proxy values against the committed DB
    rows.

    NOTE the __eq__ is based on the attributes list, but the __gt__ and __lt__
    intended for sorting objects is based on the assumption that all our DB
    objects have an "id" attribute.
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def clone(cls, template) -> "FakeRow":
        new = cls()
        for k, v in template.__dict__.items():
            if not k.startswith("_"):
                setattr(new, k, v)
        return new

    def str(self) -> str:
        return f"Row({','.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"

    def __eq__(self, entity) -> bool:
        return all(
            [
                getattr(self, x) == getattr(entity, x)
                for x in entity.__dict__.keys()
                if not x.startswith("_")
            ]
        )

    def __gt__(self, entity) -> bool:
        return self.id > entity.id

    def __lt__(self, entity) -> bool:
        return self.id < entity.id


class FakeQuery:
    """
    Model the SQLAlchemy query operations by reducing the list of known
    committed DB values based on filter expressions.
    """

    def __init__(self, session: "FakeSession"):
        """
        Set up the query using a copy of the full list of known DB objects.

        Args:
            session: The associated fake session object
        """
        self.selected = list(session.known.values())
        self.session = session

    def filter_by(self, **kwargs) -> "FakeQuery":
        """
        Reduce the list of matching DB objects by matching against the two
        main columns.

        Args:
            kwargs: Standard SQLAlchemy signature
                key: if present, select by key
                value: if present, select by value

        Returns:
            The query so filters can be chained
        """
        for s in self.selected:
            for k, v in kwargs.items():
                if k in s.__dict__ and v != getattr(s, k):
                    self.selected.remove(s)
        return self

    def order_by(self, column: Column) -> "FakeQuery":
        # print(f"ORDER BY {type(column).__name__}: {column!r}")
        # for x in dir(column):
        #     print(f"  {x}: {type(getattr(column, x)).__name__} ({getattr(column, x)})")
        self.selected.sort(key=lambda o: getattr(o, column.key))
        return self

    def all(self) -> list[Database.Base]:
        """
        Return all selected records
        """
        return self.selected

    def first(self) -> Optional[Database.Base]:
        """
        Return the first match, or None if there are none left.
        """
        return self.selected[0] if self.selected else None


class FakeSession:
    """
    Mock a SQLAlchemy Session for testing.
    """

    def __init__(self, cls):
        """
        Initialize the context of the session.

        NOTE: 'raise_on_commit' can be set by a caller to cause an exception
        during the next commit operation. The exception should generally be
        a subclass of the SQLAlchemy IntegrityError. This is a "one shot" and
        will be reset when the exception is raised.
        """
        self.id = 1
        self.cls = cls
        self.added: list[Database.Base] = []
        self.known: dict[int, Database.Base] = {}
        self.committed: dict[int, FakeRow] = {}
        self.rolledback = 0
        self.queries: list[FakeQuery] = []
        self.raise_on_commit: Optional[Exception] = None

    def query(self, *entities, **kwargs) -> FakeQuery:
        """
        Perform a mocked query on the session, setting up the query context
        and returning it

        Args:
            entities: The SQLAlchemy entities on which we're operating
            kwargs: Additional SQLAlchemy parameters

        Returns:
            A mocked query object
        """
        q = FakeQuery(self)
        self.queries.append(q)
        return q

    def add(self, instance: Database.Base):
        """
        Add a DB object to a list for testing

        Args:
            instance: A DB object
        """
        self.added.append(instance)

    def commit(self):
        """
        Mock a commit operation on the DB session. If the 'raise_on_commit'
        property has been set, "fail" by raising the exception. Otherwise,
        mock a commit by updating any cached "committed" values if the "known"
        proxy objects have changed, and record any new "added" objects.
        """
        if self.raise_on_commit:
            exc = self.raise_on_commit
            self.raise_on_commit = None
            raise exc
        for k, object in self.known.items():
            self.committed[k] = FakeRow.clone(object)
        for a in self.added:
            a.id = self.id
            self.id += 1
            for c in a.__table__._columns:
                if c.default:
                    default = c.default
                    # print(f"{type(object).__name__}.{c.name}({type(default).__name__}) default:")
                    # for x in dir(default):
                    #     print(f"  {x}: {type(getattr(default, x)).__name__} ({getattr(default, x)})")
                    if default.is_scalar:
                        setattr(a, c.name, default.arg)
                    elif default.is_callable:
                        setattr(a, c.name, default.arg(None))
            self.known[a.id] = a
            self.committed[a.id] = FakeRow.clone(a)
        self.added = []

    def rollback(self):
        """
        Just record that rollback was called, since we always raise an error
        before changing anything during the mocked commit.
        """
        self.rolledback += 1

        # Clear the proxy state by removing any new objects that weren't yet
        # committed, and "rolling back" any proxy values that were updated
        # from the committed values.
        self.added = []
        for k in self.committed:
            self.known[k] = self.cls(
                **{
                    k: v
                    for k, v in self.committed[k].__dict__.items()
                    if not k.startswith("_")
                }
            )
