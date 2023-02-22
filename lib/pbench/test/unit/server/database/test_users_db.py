import pytest
from sqlalchemy.exc import IntegrityError

from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.users import User, UserDuplicate, UserSqlError
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
            oidc_id="12345",
            username="dummy",
        )
        dummy_user.add()
        return dummy_user

    def test_construct(self, fake_db):
        """Test User db contructor"""
        user = self.add_dummy_user(fake_db)
        assert user.username == "dummy"
        assert user.id == 1
        assert user.oidc_id == "12345"

        expected_commits = [FakeRow.clone(user)]
        self.session.check_session(queries=0, committed=expected_commits)
        self.session.reset_context()

    def test_is_admin(self, fake_db):
        user = User(oidc_id="12345", username="dummy_admin", roles="ADMIN")
        user.add()
        assert user.is_admin()
        user1 = User(oidc_id="12346", username="non_admin")
        user1.add()
        assert not user1.is_admin()

        expected_commits = [FakeRow.clone(user), FakeRow.clone(user1)]
        self.session.check_session(queries=0, committed=expected_commits)
        self.session.reset_context()

    def test_user_survives_dataset_delete(self, fake_db):
        """The User isn't automatically removed when the referenced
        dataset is deleted.
        """
        self.add_dummy_user(fake_db)
        user = User.query(id=1)

        expected_commits = [FakeRow.clone(user)]
        self.session.check_session(
            queries=1, committed=expected_commits, filters=["id=1"]
        )

        ds = Dataset(owner=user.username, name="fio", resource_id="deadbeef")
        ds.add()
        expected_commits.append(FakeRow.clone(ds))

        self.session.check_session(
            queries=1, committed=expected_commits, filters=["username=dummy"]
        )
        ds.delete()
        assert user
        self.session.reset_context()

    def test_construct_duplicate(self, fake_db):
        """Test handling of User record duplicate value error"""
        self.session.raise_on_commit = IntegrityError(
            statement="", params="", orig=FakeDBOrig("UNIQUE constraint")
        )
        with pytest.raises(
            UserDuplicate,
            match="Duplicate user setting in {'username': 'dummy', 'id': None}: UNIQUE constraint",
        ):
            self.add_dummy_user(fake_db)
        self.session.check_session(rolledback=1)
        self.session.reset_context()

    def test_user_update(self, fake_db):
        """Test updating user roles"""

        data = {"roles": "NEW_ROLE"}
        TestUsers.add_dummy_user(fake_db)

        user = User.query(id=1)
        user.update(**data)
        assert user.roles == ["NEW_ROLE"]

        expected_commits = [FakeRow.clone(user)]
        self.session.check_session(
            queries=1, committed=expected_commits, filters=["id=1"]
        )
        self.session.reset_context()

    def test_user_delete(self, fake_db):
        """Test deleting the user from the User table"""
        self.add_dummy_user(fake_db)
        user = User.query(id=1)
        expected_commits = [FakeRow.clone(user)]
        self.session.check_session(
            queries=1, filters=["id=1"], committed=expected_commits
        )
        assert user.username == "dummy"
        assert user.id == 1
        user.delete()
        self.session.check_session(queries=0, filters=[], committed=[])

    def test_delete_exception(self, fake_db):
        """Test exception raised during the delete operation"""
        user = User(
            oidc_id="12345",
            username="dummy",
        )
        with pytest.raises(
            UserSqlError,
            match=r"deleting",
        ):
            user.delete()
        self.session.reset_context()
