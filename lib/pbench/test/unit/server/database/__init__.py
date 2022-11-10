"""The SQLAlchemy mock infrastructure here is not completely generalized, but
is currently sufficient to support the ServerConfig and Audit DB unit tests.
"""

import operator
from typing import Any, Callable, Iterable, Optional

from sqlalchemy import Column
from sqlalchemy.exc import SQLAlchemyError

from pbench.server.database.database import Database


def dumpem(object: Any, depth: int = 0, max_depth: int = 20):
    """
    Useful recursive function to help debug SQLAlchemy's deep and mostly not
    documented class hierarchy! NOTE: this can generate an enormous amount of
    output and should be used carefully. While simple in principle, it's worth
    archiving for future use.

    The recursion depth is limited to 20 by default. That's arbitrary, but we
    don't want to overflow.

    Args:
        object: Any Python object
        depth: indentation levels (two spaces)
        max_depth: maximum recursion depth
    """
    if depth > max_depth:
        return
    indent = " " * (depth * 2)
    print(f"{indent}'{object}' [{type(object).__name__}]")
    if hasattr(object, "items") or hasattr(object, "__dict__"):
        # Either a map-style object (dict, immutabledict) or a non-builtin
        # object (__dict__) has a set of key/value pairs we want to expose:
        # we can handle these more or less the same. If the value of each
        # isn't "obviously trivial" recurse to format it as well.
        d = object if hasattr(object, "items") else object.__dict__
        for n, v in d.items():
            print(f"{indent}  '{n}'='{v}' [{type(v).__name__}]")
            if not isinstance(v, (type(None), bool, int, float, str, Callable)):
                dumpem(v, depth + 2, max_depth)
    elif isinstance(object, Iterable) and not isinstance(object, str):
        # If the object is iterable, we want to iterate through all
        # values.
        for e in object:
            dumpem(e, depth + 1, max_depth)


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

    def __init__(self, cls: Optional[type[Database.Base]] = None, **kwargs):
        self.cls = cls
        for k, v in kwargs.items():
            setattr(self, k, v)

    def _columns(self) -> list[str]:
        return [c.name for c in self.cls.__table__._columns] if self.cls else dir(self)

    @classmethod
    def clone(cls, template: Database.Base) -> "FakeRow":
        new = cls(cls=type(template))
        for c in new._columns():
            setattr(new, c, getattr(template, c))
        return new

    def __repr__(self) -> str:
        return (
            "Row(" + ",".join(f"{c}={getattr(self, c)}" for c in self._columns()) + ")"
        )

    def __eq__(self, entity) -> bool:
        return (type(self) is type(entity) or type(entity) is self.cls) and all(
            getattr(self, x) == getattr(entity, x) for x in self._columns()
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

    """Translate built-in operator functions to symbols"""
    OPS = {
        operator.lt: "<",
        operator.le: "<=",
        operator.eq: "=",
        operator.ne: "!=",
        operator.ge: ">=",
        operator.gt: ">",
    }

    def __init__(self, session: "FakeSession"):
        """
        Set up the query using a copy of the full list of known DB objects.

        Args:
            session: The associated fake session object
        """
        self.selected = list(session.known.values())
        self.session = session
        self.filters = []

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
        self.selected = [
            s
            for s in self.selected
            if not any(
                k in s.__dict__ and v != getattr(s, k) for k, v in kwargs.items()
            )
        ]
        self.session.filters.append(",".join(f"{n}={v}" for n, v in kwargs.items()))
        return self

    def filter(self, *criteria) -> "FakeQuery":
        """
        Record the context of a filter operation. Unlike the simple key=value
        semantics of filter_by, we don't try to implement the filtering: a unit
        test using the filter operation should instead compare the list of
        filter representations directly.

        NOTE: the SQL/column syntax here is harder to emulate than the simple
        key=value semantics of filter_by, and while we interpret the SQLAlchemy
        BinaryExpression enough to represent it as a string, we don't attempt to
        emulate the actual filter behavior.

        Args:
            criteria: A set of column expressions like 'Table.column >= foo'.
        """
        filters = []
        for c in criteria:
            op = self.OPS[c.operator] if c.operator in self.OPS else c.operator
            f = f"{c.left} {op} {c.right.value}"
            filters.append(f)
        self.session.filters.append(", ".join(filters))
        return self

    def order_by(self, column: Column) -> "FakeQuery":
        self.selected.sort(key=lambda o: getattr(o, column.key))
        return self

    def all(self) -> list[Database.Base]:
        """
        Return all selected records alphabetically sorted to help with
        comparison. (Generally the order of filtering is not important.)
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

    throw_query = False

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
        self.filters: list[str] = []
        self.raise_on_commit: Optional[Exception] = None

    def reset_context(self):
        """Reset the queries and filters for the session between unit test
        cases, along with forced errors."""
        self.queries = []
        self.filters = []
        self.raise_on_commit = None
        __class__.throw_query = False

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
        if self.throw_query:
            raise SQLAlchemyError("test", "because")
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
                    n: getattr(self.committed[k], n)
                    for n in self.committed[k]._columns()
                }
            )

    def check_session(
        self,
        queries: int = 0,
        committed: Optional[list[FakeRow]] = [],
        filters: Optional[list[str]] = [],
        rolledback=0,
    ):
        """
        Encapsulate the common checks we want to make after running test cases.

        NOTE: The queries and rolledback checks default to 0 count, and will
        fail if queries or rolled back commits have occurred. The committed and
        filters checks default to an empty list; these will also fail if any
        commits or filtered queries have occurred, but these checks can be
        disabled by specifying None.

        Args:
            queries: A count of queries we expect to have been made
            committed: A list of FakeRow objects we expect to have been
                committed
            filters: A list of expected filter terms
            rolledback: True if we expect rollback to have been called
        """

        # Check the number of queries we've created, if specified
        assert (
            len(self.queries) == queries
        ), f"Expected {queries} queries, got {len(self.queries)}"

        # Check the filters we imposed. We sort the filters because normally
        # the end result doesn't depend on the order they're applied.
        # NOTE: this generally presumes we're only generating a single query,
        # so that all filters are associated with that query. If this becomes
        # important for testing some DB object, we'd need to make the filters
        # parameter into a list of lists to be compared against individual
        # queries.
        assert filters is None or sorted(filters) == sorted(self.filters)

        # 'added' is an internal "dirty" list between 'add' and 'commit' or
        # 'rollback'. We test that 'commit' moves elements to the committed
        # state and 'rollback' clears the list. We don't ever expect to see
        # anything on this list.
        assert not self.added

        # Check that the 'committed' list (which stands in for the actual DB
        # table) contains the expected rows.
        assert committed is None or sorted(self.committed.values()) == sorted(committed)

        # Check whether we've rolled back a transaction due to failure.
        assert self.rolledback == rolledback
        self.reset_context()
