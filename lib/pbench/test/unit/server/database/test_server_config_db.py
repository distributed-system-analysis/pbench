from typing import List

import pytest
from sqlalchemy.exc import IntegrityError

from pbench.server.database.database import Database
from pbench.server.database.models.server_config import (
    ServerConfig,
    ServerConfigBadKey,
    ServerConfigBadValue,
    ServerConfigDuplicate,
    ServerConfigMissingKey,
    ServerConfigNullKey,
)
from pbench.test.unit.server.database import FakeDBOrig, FakeRow, FakeSession


class TestServerConfig:
    session = None

    def check_session(self, queries=0, committed: List[FakeRow] = [], rolledback=0):
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
        self.session = FakeSession(ServerConfig)
        with monkeypatch.context() as m:
            m.setattr(Database, "db_session", self.session)
            Database.Base.config = server_config
            yield

    def test_bad_key(self):
        """Test server config parameter key validation"""
        with pytest.raises(ServerConfigBadKey) as exc:
            ServerConfig.create(key="not-a-key", value="no-no")
        assert str(exc.value) == "Configuration key 'not-a-key' is unknown"

    def test_construct(self):
        """Test server config parameter constructor"""
        config = ServerConfig(key="dataset-lifetime", value="2")
        assert config.key == "dataset-lifetime"
        assert config.value == "2"
        assert str(config) == "dataset-lifetime: '2'"
        self.check_session()

    def test_create(self):
        """Test server config parameter creation"""
        config = ServerConfig.create(key="dataset-lifetime", value="2")
        assert config.key == "dataset-lifetime"
        assert config.value == "2"
        assert str(config) == "dataset-lifetime: '2'"
        self.check_session(committed=[FakeRow(id=1, key="dataset-lifetime", value="2")])

    def test_construct_duplicate(self):
        """Test server config parameter constructor"""
        ServerConfig.create(key="dataset-lifetime", value=1)
        self.check_session(committed=[FakeRow(id=1, key="dataset-lifetime", value="1")])
        with pytest.raises(ServerConfigDuplicate) as e:
            self.session.raise_on_commit = IntegrityError(
                statement="", params="", orig=FakeDBOrig("UNIQUE constraint")
            )
            ServerConfig.create(key="dataset-lifetime", value=2)
        assert str(e).find("dataset-lifetime") != -1
        self.check_session(
            committed=[FakeRow(id=1, key="dataset-lifetime", value="1")], rolledback=1
        )

    def test_construct_null(self):
        """Test server config parameter constructor"""
        with pytest.raises(ServerConfigNullKey):
            self.session.raise_on_commit = IntegrityError(
                statement="", params="", orig=FakeDBOrig("NOT NULL constraint")
            )
            ServerConfig.create(key="dataset-lifetime", value=2)
        self.check_session(
            rolledback=1,
        )

    def test_get(self):
        """Test that we can retrieve what we set"""
        config = ServerConfig.create(key="dataset-lifetime", value="2")
        result = ServerConfig.get(key="dataset-lifetime")
        assert config == result
        self.check_session(
            committed=[FakeRow(id=1, key="dataset-lifetime", value="2")], queries=1
        )

    def test_update(self):
        """Test that we can update an existing configuration setting"""
        config = ServerConfig.create(key="dataset-lifetime", value="2")
        self.check_session(committed=[FakeRow(id=1, key="dataset-lifetime", value="2")])
        config.value = "5"
        config.update()
        self.check_session(committed=[FakeRow(id=1, key="dataset-lifetime", value="5")])
        result = ServerConfig.get(key="dataset-lifetime")
        assert config == result
        self.check_session(
            committed=[FakeRow(id=1, key="dataset-lifetime", value="5")], queries=1
        )

    def test_set(self):
        """
        Test that we can use set both to create and update configuration
        settings
        """
        config = ServerConfig.set(key="dataset-lifetime", value="40 days")
        result = ServerConfig.get(key="dataset-lifetime")
        assert config == result
        assert config.value == "40"
        ServerConfig.set(key="dataset-lifetime", value=120)
        result = ServerConfig.get(key="dataset-lifetime")
        assert result.value == "120"

        # NOTE: each `get` does a query, plus each `set` checks whether the
        # key already exists: 2 get + 2 set == 4 queries
        self.check_session(
            committed=[FakeRow(id=1, key="dataset-lifetime", value="120")], queries=4
        )

    def test_missing(self):
        """Check that 'create' complains about a missing key"""
        with pytest.raises(ServerConfigMissingKey):
            ServerConfig.create(key=None, value=None)

    def test_get_all_default(self):
        """
        Test get_all when no values have been set. It should return all the
        defined keys, but with None values.
        """
        assert ServerConfig.get_all() == {
            "dataset-lifetime": "3650",
            "server-state": {"status": "enabled"},
            "server-banner": None,
        }

    def test_get_all(self):
        """
        Set values and make sure they're all reported correctly
        """
        ServerConfig.create(key="dataset-lifetime", value="2")
        ServerConfig.create(key="server-state", value={"status": "enabled"})
        ServerConfig.create(key="server-banner", value={"message": "Mine"})
        assert ServerConfig.get_all() == {
            "dataset-lifetime": "2",
            "server-state": {"status": "enabled"},
            "server-banner": {"message": "Mine"},
        }

    @pytest.mark.parametrize(
        "value,expected",
        [
            (2, "2"),
            ("4", "4"),
            ("999999999", "999999999"),
            ("10 days", "10"),
            ("1day", "1"),
            ("1       days", "1"),
            ("1 day", "1"),
        ],
    )
    def test_lifetimes(self, value, expected):
        """
        Test some lifetimes that should be OK
        """
        config = ServerConfig.create(key="dataset-lifetime", value=value)
        assert config.value == expected

    @pytest.mark.parametrize(
        "value",
        [
            "string",
            ["list"],
            ("tuple"),
            {"dict": "ionary"},
            "1d",
            "1da",
            "9999999999",
            "1 daysies",
            "1 days, 10:15:20",
        ],
    )
    def test_bad_lifetimes(self, value):
        """
        Test some lifetime values that aren't legal
        """
        with pytest.raises(ServerConfigBadValue) as exc:
            ServerConfig.create(key="dataset-lifetime", value=value)
        assert exc.value.value == value

    @pytest.mark.parametrize(
        "key,value",
        [
            ("server-state", {"status": "enabled"}),
            ("server-state", {"status": "enabled", "message": "All OK"}),
            (
                "server-state",
                {
                    "status": "disabled",
                    "message": "Not so good",
                    "up_again": "tomorrow",
                },
            ),
            (
                "server-state",
                {
                    "status": "readonly",
                    "message": "Look but don't touch",
                    "reason": "rebuilding",
                },
            ),
            (
                "server-banner",
                {"message": "Perf & Scale Pbench server", "contact": "Call Pete"},
            ),
            (
                "server-banner",
                {"message": "You should see this", "url": "http://nowhere"},
            ),
        ],
    )
    def test_create_state_and_banner(self, key, value):
        """Test server state and banner setting"""
        config = ServerConfig.create(key=key, value=value)
        assert config.key == key
        assert config.value == value

    @pytest.mark.parametrize(
        "value",
        [
            None,
            1,
            4.000,
            True,
            "yes",
            ["a", "b"],
            {"banner": "Must have 'status' key"},
            {"status": "nonsense", "message": "This uses a bad 'status' value"},
            {"status": "disabled", "banner": "'disabled' requires a message'"},
        ],
    )
    def test_bad_state(self, value):
        """
        A "server-state" value must include at least "status" and if the value
        isn't "enabled" must also contain "message"
        """
        with pytest.raises(ServerConfigBadValue) as exc:
            ServerConfig.create(key="server-state", value=value)
        assert exc.value.value == value

    @pytest.mark.parametrize("value", [1, True, "yes", ["a", "b"], {"banner": "xyzzy"}])
    def test_bad_banner(self, value):
        """
        A "server-banner" value must include at least "message"
        """
        with pytest.raises(ServerConfigBadValue) as exc:
            ServerConfig.create(key="server-banner", value=value)
        assert exc.value.value == value
