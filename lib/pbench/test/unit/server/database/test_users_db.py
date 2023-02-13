import datetime

from freezegun.api import freeze_time
import pytest
from sqlalchemy.exc import IntegrityError

from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.users import (
    User,
    UserDuplicate,
    UserError,
    UserSqlError,
)
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
            oidc_id=12345,
            username="dummy",
            profile={
                "user": {
                    "email": "dummy@example.com",
                    "first_name": "Dummy",
                    "last_name": "Account",
                },
                "server": {
                    "roles": [],
                    "registered_on": datetime.datetime.now().strftime("%m/%d/%Y"),
                },
            },
        )
        dummy_user.add()
        return dummy_user

    def test_construct(self, fake_db):
        """Test User db contructor"""
        with freeze_time("1970-01-01"):
            user = self.add_dummy_user(fake_db)
        assert user.username == "dummy"
        assert user.id == 1
        assert user.get_json() == {
            "username": "dummy",
            "profile": {
                "user": {
                    "email": "dummy@example.com",
                    "first_name": "Dummy",
                    "last_name": "Account",
                },
                "server": {
                    "roles": [],
                    "registered_on": "01/01/1970",
                },
            },
        }

        expected_commits = [FakeRow.clone(user)]
        self.session.check_session(queries=0, committed=expected_commits)
        self.session.reset_context()

    def test_is_admin(self, fake_db):
        profile = {
            "user": {
                "email": "dummy@example.com",
                "first_name": "Dummy",
                "last_name": "Account",
            },
            "server": {
                "roles": ["ADMIN"],
                "registered_on": datetime.datetime.now().strftime("%m/%d/%Y"),
            },
        }
        user = User(
            oidc_id=12345,
            username="dummy_admin",
            profile=profile,
        )
        user.add()
        assert user.is_admin()
        profile["server"]["roles"] = ["NON_ADMIN"]
        user1 = User(
            oidc_id=12346,
            username="non_admin",
            profile=profile,
        )
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
            match="Duplicate user setting in {'id': None, 'oidc_id': 12345, 'username': 'dummy', .*?: UNIQUE constraint",
        ):
            self.add_dummy_user(fake_db)
        self.session.check_session(rolledback=1)
        self.session.reset_context()

    @pytest.mark.parametrize(
        "case, data",
        [
            (1, {"user.department": "Perf_Scale", "user.company.name": "Red Hat"}),
            (2, {"user": {"email": "new_dummy@example.com"}}),
            (3, {"user": {"company": {"location": "Westford"}}}),
        ],
    )
    def test_user_update(self, db_session, fake_db, case, data):
        """Test updating user profile with different types of kwargs"""
        TestUsers.add_dummy_user(db_session)
        user = User.query(id=1)
        valid_dict = user.form_valid_dict(**data)
        user.update(new_profile=valid_dict)
        if case == 1:
            assert user.profile["user"]["department"] == "Perf_Scale"
            assert user.profile["user"]["company"]["name"] == "Red Hat"
            assert user.profile["user"]["email"] == "dummy@example.com"
        elif case == 2:
            assert user.profile["user"]["email"] == "new_dummy@example.com"
        elif case == 3:
            assert user.profile["user"]["company"]["location"] == "Westford"

        expected_commits = [FakeRow.clone(user)]
        self.session.check_session(
            queries=1, committed=expected_commits, filters=["id=1"]
        )
        self.session.reset_context()

    @pytest.mark.parametrize(
        "data",
        [{"server.key": "value"}, {"server.role": ["value"]}, {"server": ""}],
    )
    def test_user_update_bad_key(self, db_session, fake_db, data):
        """Test updating user with non-updatable key:value pair"""
        TestUsers.add_dummy_user(db_session)
        user = User.query(id=1)
        with pytest.raises(
            UserError,
            match=r"User profile key 'server.*?' is not supported",
        ):
            valid_dict = user.form_valid_dict(**data)
            user.update(new_profile=valid_dict)
        self.session.reset_context()

    def test_user_update_bad_format(self, fake_db):
        """Test updating user with bad key formatting"""
        TestUsers.add_dummy_user(fake_db)
        user = User.query(id=1)
        data = {"user.key": "value", "user.key.key2": "value2"}
        with pytest.raises(
            UserError,
            match=r"Key value for 'key' in profile is not a JSON object",
        ):
            valid_dict = user.form_valid_dict(**data)
            user.update(new_profile=valid_dict)
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

    def test_delete_exception(self):
        """Test exception raised during the delete operation"""
        user = User(
            oidc_id=12345,
            username="dummy",
            profile={
                "user": {
                    "email": "dummy@example.com",
                    "first_name": "Dummy",
                    "last_name": "Account",
                },
                "server": {
                    "roles": [],
                    "registered_on": datetime.datetime.now().strftime("%m/%d/%Y"),
                },
            },
        )
        with pytest.raises(
            UserSqlError,
            match=r"deleting",
        ):
            user.delete()
        self.session.reset_context()
