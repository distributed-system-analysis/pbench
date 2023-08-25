import datetime

import dateutil.parser
from freezegun.api import freeze_time
import pytest
from sqlalchemy.exc import DatabaseError, IntegrityError

from pbench.server import OperationCode
from pbench.server.database.database import Database
from pbench.server.database.models.audit import (
    Audit,
    AuditDuplicate,
    AuditNullKey,
    AuditSqlError,
    AuditStatus,
)
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.users import User
from pbench.test.unit.server.database import FakeDBOrig, FakeRow, FakeSession


class TestAudit:
    session = None

    @pytest.fixture()
    def fake_db(self, monkeypatch, server_config):
        """
        Fixture to mock a DB session for testing.

        We patch the SQLAlchemy db_session to our fake session. We also store a
        server configuration object directly on the Database.Base (normally
        done during DB initialization) because that can't be monkeypatched.
        """
        __class__.session = FakeSession(Audit)
        monkeypatch.setattr(Database, "db_session", __class__.session)
        Database.Base.config = server_config
        yield monkeypatch

    def test_construct(self, fake_db):
        """Test Audit record constructor"""
        audit = Audit(
            name="mine", operation=OperationCode.CREATE, status=AuditStatus.BEGIN
        )
        assert audit.name == "mine"
        assert audit.operation is OperationCode.CREATE
        assert audit.status is AuditStatus.BEGIN
        self.session.check_session()

    def test_create(self, fake_db):
        """Test Audit record creation"""
        audit = Audit.create(
            name="mine", operation=OperationCode.CREATE, status=AuditStatus.BEGIN
        )
        assert audit.name == "mine"
        assert audit.operation == OperationCode.CREATE
        assert audit.status == AuditStatus.BEGIN
        self.session.check_session(committed=[FakeRow.clone(audit)])

    def test_construct_null(self, fake_db):
        """Test handling of Audit record null value error"""
        self.session.raise_on_commit = IntegrityError(
            statement="", params="", orig=FakeDBOrig("not null constraint")
        )
        with pytest.raises(AuditNullKey):
            Audit.create(operation=OperationCode.CREATE, status=AuditStatus.BEGIN)
        self.session.check_session(rolledback=1)

    def test_construct_duplicate(self, fake_db):
        """Test handling of Audit record duplicate value error"""
        self.session.raise_on_commit = IntegrityError(
            statement="", params="", orig=FakeDBOrig("UNIQUE constraint")
        )
        with pytest.raises(AuditDuplicate):
            Audit.create(id=1, operation=OperationCode.CREATE, status=AuditStatus.BEGIN)
        self.session.check_session(rolledback=1)

    def test_construct_error(self, fake_db):
        """Test handling of Audit record create with a general error"""
        self.session.raise_on_commit = DatabaseError(
            statement="", params="", orig=FakeDBOrig("something else")
        )
        with pytest.raises(AuditSqlError):
            Audit.create(id=1, operation=OperationCode.CREATE, status=AuditStatus.BEGIN)
        self.session.check_session(rolledback=1)

    def test_sequence(self, fake_db):
        attr = {"message": "the framistan is borked"}
        ds = Dataset(id=1, name="test", resource_id="hash")
        with freeze_time("2022-01-01 00:00:00 UTC") as f:
            root = Audit.create(
                name="upload",
                dataset=ds,
                operation=OperationCode.CREATE,
                status=AuditStatus.BEGIN,
            )
            f.tick(delta=datetime.timedelta(hours=5))
            other = Audit.create(root=root, status=AuditStatus.FAILURE, attributes=attr)
        self.session.check_session(
            committed=[FakeRow.clone(root), FakeRow.clone(other)]
        )

    def test_override(self, fake_db):
        attr = {"message": "the framistan is borked"}
        ds = Dataset(id=1, name="test", resource_id="md5")
        with freeze_time("2022-01-01 00:00:00 UTC") as f:
            root = Audit.create(
                name="meta",
                dataset=ds,
                operation=OperationCode.CREATE,
                status=AuditStatus.BEGIN,
            )
            f.tick(delta=datetime.timedelta(hours=5))
            other = Audit.create(
                root=root,
                status=AuditStatus.FAILURE,
                attributes=attr,
                object_id="5",
                name="secundo",
                user_name="tester",
            )
        assert other.as_json() == {
            "attributes": attr,
            "id": 2,
            "name": "secundo",
            "object_id": "5",
            "object_name": "test",
            "object_type": "DATASET",
            "operation": "CREATE",
            "reason": None,
            "root_id": 1,
            "status": "FAILURE",
            "timestamp": "2022-01-01T05:00:00+00:00",
            "user_id": None,
            "user_name": "tester",
        }
        self.session.check_session(
            committed=[FakeRow.clone(root), FakeRow.clone(other)]
        )

    def test_exceptional_query(self, fake_db):
        FakeSession.throw_query = True
        with pytest.raises(AuditSqlError):
            Audit.query(user_name="imme")
        self.session.reset_context()

    def test_queries(self, fake_db):
        attr1 = {"message": "the framistan is borked"}
        attr2 = {"message": "OK", "updated": {"dataset.access": "public"}}
        ds1 = Dataset(id=1, name="testy", resource_id="md5.1")
        ds2 = Dataset(id=2, name="tasty", resource_id="md5.2")
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
            done1 = Audit.create(
                root=root1, status=AuditStatus.FAILURE, attributes=attr1
            )

            f.tick(delta=datetime.timedelta(minutes=40))
            done2 = Audit.create(
                root=root2, status=AuditStatus.SUCCESS, attributes=attr2
            )

        # Try some queries. The mocked query returns the ordered list of
        # filters passed to the database engine: we want to confirm that the
        # expected filters were run, and there's no point in trying to mock the
        # behavior of those filters.
        expected_commits = [
            FakeRow.clone(root1),
            FakeRow.clone(done1),
            FakeRow.clone(root2),
            FakeRow.clone(done2),
        ]

        Audit.query(user_name="imme")
        self.session.check_session(
            queries=1, committed=expected_commits, filters=["user_name=imme"]
        )

        Audit.query(object_name="testy")

        self.session.check_session(
            queries=1, committed=expected_commits, filters=["object_name=testy"]
        )

        Audit.query(dataset=ds1)
        self.session.check_session(
            queries=1,
            committed=None,
            filters=["audit.object_type = AuditType.DATASET, audit.object_id = md5.1"],
        )

        Audit.query(timestamp=dateutil.parser.parse("2022-01-01 00:00:00 UTC"))
        self.session.check_session(
            queries=1,
            committed=expected_commits,
            filters=["timestamp=2022-01-01 00:00:00+00:00"],
        )

        Audit.query(start=dateutil.parser.parse("2022-01-01 04:00:00 UTC"))
        self.session.check_session(
            queries=1,
            committed=expected_commits,
            filters=["audit.timestamp >= 2022-01-01 04:00:00+00:00"],
        )

        Audit.query(
            start=dateutil.parser.parse("2022-01-01 01:00:00 UTC"),
            end=dateutil.parser.parse("2022-01-01 04:00:00 UTC"),
        )
        self.session.check_session(
            queries=1,
            committed=expected_commits,
            filters=[
                "audit.timestamp >= 2022-01-01 01:00:00+00:00",
                "audit.timestamp <= 2022-01-01 04:00:00+00:00",
            ],
        )

        Audit.query(
            name="test",
            start=dateutil.parser.parse("2022-01-01 01:00:00 UTC"),
            end=dateutil.parser.parse("2022-01-01 04:00:00 UTC"),
        )
        self.session.check_session(
            queries=1,
            committed=expected_commits,
            filters=[
                "name=test",
                "audit.timestamp >= 2022-01-01 01:00:00+00:00",
                "audit.timestamp <= 2022-01-01 04:00:00+00:00",
            ],
        )
