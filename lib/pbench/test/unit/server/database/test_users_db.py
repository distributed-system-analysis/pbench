import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset, DatasetNotFound
from pbench.server.database.models.users import User, UserDuplicate
from pbench.test.unit.server.database import FakeDBOrig, FakeRow, FakeSession


class TestUsers:
    session = None

    @pytest.fixture()
    def fake_db(self, monkeypatch, server_config):
        """
        Fixture to mock a DB session for testing.

        We patch the SQLAlchemy db_session to our fake session. We also store a
        server configuration object directly on the Database.Base (normally
        done during DB initialization) because that can't be monkeypatched.
        """
        __class__.session = FakeSession(User)
        monkeypatch.setattr(Database, "db_session", __class__.session)
        Database.Base.config = server_config
        yield monkeypatch

    @staticmethod
    def add_dummy_user(fake_db):
        dummy_user = User(
            id=str(uuid.uuid4()),
            username="dummy",
        )
        dummy_user.add()
        return dummy_user

    def test_construct(self, fake_db):
        """Test User db contructor"""
        user = self.add_dummy_user(fake_db)
        assert user.username == "dummy"

        expected_commits = [FakeRow.clone(user)]
        self.session.check_session(queries=0, committed=expected_commits)
        self.session.reset_context()

    def test_is_admin(self, fake_db):
        uuid4 = str(uuid.uuid4())
        user = User(id=uuid4, username="dummy_admin", roles=["ADMIN"])
        user.add()
        assert user.is_admin()
        assert user.id == uuid4
        user1 = User(id="1", username="non_admin")
        user1.add()
        assert not user1.is_admin()

        expected_commits = [FakeRow.clone(user), FakeRow.clone(user1)]
        self.session.check_session(queries=0, committed=expected_commits)
        self.session.reset_context()

    def test_user_survives_dataset_real_session(self, db_session, create_user):
        """The User isn't automatically removed when the referenced
        dataset is deleted.
        """
        user = create_user
        ds = Dataset(owner=user, name="fio", resource_id="deadbeef")
        ds.add()
        ds.delete()
        with pytest.raises(DatasetNotFound):
            Dataset.query(resource_id=ds.resource_id)
        assert user == User.query(username=user.username)

    def test_construct_duplicate(self, fake_db):
        """Test handling of User record duplicate value error"""
        exception = IntegrityError(
            statement="", params="", orig=FakeDBOrig("unique constraint")
        )
        self.session.raise_on_commit = exception
        with pytest.raises(
            UserDuplicate,
            match="Duplicate user",
        ) as exc:
            self.add_dummy_user(fake_db)
        assert len(exc.value.args) == 2
        assert exc.value.args[0] == f"Duplicate user: '{exception}'"
        assert exc.value.args[1]["operation"] == "add"
        assert exc.value.args[1]["user"].username == "dummy"
        self.session.check_session(rolledback=1)
        self.session.reset_context()

    def test_user_update(self, fake_db):
        """Test updating user roles"""

        TestUsers.add_dummy_user(fake_db)

        user = User.query(username="dummy")
        user.update(roles=["NEW_ROLE"])
        assert user.roles == ["NEW_ROLE"]
        assert user._roles == "NEW_ROLE"

        expected_commits = [FakeRow.clone(user)]
        self.session.check_session(
            queries=1, committed=expected_commits, filters=["username=dummy"]
        )
        self.session.reset_context()
