import datetime

from freezegun.api import freeze_time
import pytest
from sqlalchemy.exc import IntegrityError

from pbench.server import OperationCode
from pbench.server.database.database import Database
from pbench.server.database.models.audit import Audit, AuditNullKey, AuditStatus
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.users import User
from pbench.test.unit.server.database import FakeDBOrig, FakeRow, FakeSession


class TestAudit:
    session = None

    def check_session(self, queries=0, committed: list[FakeRow] = [], rolledback=0):
        """
        Encapsulate the common checks we want to make after running test cases.

        Args:
            queries: A count of queries we expect to have been made
            committed: A list of FakeRow objects we expect to have been
                committed
            rolledback: True if we expect rollback to have been called
        """
        session = self.session
        assert session

        # Check the number of queries we've created
        assert len(session.queries) == queries

        # 'added' is an internal "dirty" list between 'add' and 'commit' or
        # 'rollback'. We test that 'commit' moves elements to the committed
        # state and 'rollback' clears the list. We don't ever expect to see
        # anything on this list.
        assert not session.added

        # Check that the 'committed' list (which stands in for the actual DB
        # table) contains the expected rows.
        assert sorted(list(session.committed.values())) == sorted(committed)

        # Check whether we've rolled back a transaction due to failure.
        assert session.rolledback == rolledback

    @pytest.fixture(autouse=True, scope="function")
    def fake_db(self, monkeypatch, server_config):
        """
        Fixture to mock a DB session for testing.

        We patch the SQLAlchemy db_session to our fake session. We also store a
        server configuration object directly on the Database.Base (normally
        done during DB initialization) because that can't be monkeypatched.
        """
        self.session = FakeSession(Audit)
        with monkeypatch.context() as m:
            m.setattr(Database, "db_session", self.session)
            Database.Base.config = server_config
            yield

    def test_construct(self):
        """Test Audit record constructor"""
        audit = Audit(operation=OperationCode.CREATE, status=AuditStatus.BEGIN)
        assert audit.operation is OperationCode.CREATE
        assert audit.status is AuditStatus.BEGIN
        self.check_session()

    def test_create(self):
        """Test Audit record creation"""
        audit = Audit.create(operation=OperationCode.CREATE, status=AuditStatus.BEGIN)
        assert audit.operation == OperationCode.CREATE
        assert audit.status == AuditStatus.BEGIN
        self.check_session(
            committed=[
                FakeRow(id=1, operation=OperationCode.CREATE, status=AuditStatus.BEGIN)
            ]
        )

    def test_construct_null(self):
        """Test handling of Audit record null value error"""
        with pytest.raises(AuditNullKey):
            self.session.raise_on_commit = IntegrityError(
                statement="", params="", orig=FakeDBOrig("NOT NULL constraint")
            )
            Audit.create(operation=OperationCode.CREATE, status=AuditStatus.BEGIN)
        self.check_session(
            rolledback=1,
        )

    def test_sequence(self):
        attr = {"message": "the framistan is borked"}
        ds = Dataset(id=1, name="test")
        with freeze_time("2022-01-01 00:00:00 UTC") as f:
            root = Audit.create(
                dataset=ds, operation=OperationCode.CREATE, status=AuditStatus.BEGIN
            )
            f.tick(delta=datetime.timedelta(hours=5))
            other = Audit.create(root=root, status=AuditStatus.FAILURE, attributes=attr)

        records = Audit.query()
        assert len(records) == 2
        assert records[0].id == root.id
        assert records[1].id == other.id
        assert records[0].operation == records[1].operation == OperationCode.CREATE
        assert records[0].status == AuditStatus.BEGIN
        assert records[1].status == AuditStatus.FAILURE
        assert records[0].attributes is None
        assert records[1].attributes == attr
        assert records[0].timestamp == datetime.datetime(
            year=2022,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            tzinfo=datetime.timezone.utc,
        )
        assert records[1].timestamp == datetime.datetime(
            year=2022,
            month=1,
            day=1,
            hour=5,
            minute=0,
            second=0,
            tzinfo=datetime.timezone.utc,
        )

    def test_queries(self):
        attr1 = {"message": "the framistan is borked"}
        attr2 = {"message": "OK", "updated": {"dataset.access": "public"}}
        ds1 = Dataset(id=1, name="testy")
        ds2 = Dataset(id=2, name="tasty")
        user1 = User(id=1, username="imme")
        user2 = User(id=2, username="imyou")
        with freeze_time("2022-01-01 00:00:00 UTC") as f:
            root1 = Audit.create(
                dataset=ds1,
                user=user2,
                operation=OperationCode.CREATE,
                status=AuditStatus.BEGIN,
            )

            f.tick(delta=datetime.timedelta(seconds=20))
            root2 = Audit.create(
                dataset=ds2,
                user=user1,
                operation=OperationCode.UPDATE,
                status=AuditStatus.BEGIN,
            )

            f.tick(delta=datetime.timedelta(hours=5))
            Audit.create(root=root1, status=AuditStatus.FAILURE, attributes=attr1)

            f.tick(delta=datetime.timedelta(minutes=40))
            Audit.create(root=root2, status=AuditStatus.SUCCESS, attributes=attr2)

        # Try some simplistic queries. There's not much point in trying to
        # exhaustively test queries as this ends up being more a test of the
        # SQLAlchemy engine mocks than the Audit class. All we really care
        # about here is that Audit.query() returns the results of the engine
        # query.

        records = Audit.query(user_name="imme")
        assert len(records) == 2
        assert records[0].operation is OperationCode.UPDATE
        assert records[1].operation is OperationCode.UPDATE

        records = Audit.query(object_name="testy")
        assert len(records) == 2
        assert records[0].operation is OperationCode.CREATE
        assert records[1].operation is OperationCode.CREATE

        records = Audit.query(user_id=2)
        assert len(records) == 2
        assert records[0].operation is OperationCode.CREATE
        assert records[1].operation is OperationCode.CREATE
