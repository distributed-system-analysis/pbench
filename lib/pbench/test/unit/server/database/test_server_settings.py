import pytest
from sqlalchemy.exc import IntegrityError

from pbench.server.database.database import Database
from pbench.server.database.models.server_settings import (
    ServerSetting,
    ServerSettingBadKey,
    ServerSettingBadValue,
    ServerSettingDuplicate,
    ServerSettingMissingKey,
    ServerSettingNullKey,
)
from pbench.test.unit.server.database import FakeDBOrig, FakeRow, FakeSession


class TestServerSetting:
    session = None

    @pytest.fixture(autouse=True, scope="function")
    def fake_db(self, monkeypatch, server_config):
        """
        Fixture to mock a DB session for testing.

        We patch the SQLAlchemy db_session to our fake session. We also store a
        server configuration object directly on the Database.Base (normally
        done during DB initialization) because that can't be monkeypatched.
        """
        self.session = FakeSession(ServerSetting)
        monkeypatch.setattr(Database, "db_session", self.session)
        Database.Base.config = server_config
        yield

    def test_bad_key(self):
        """Test server setting key validation"""
        with pytest.raises(ServerSettingBadKey) as exc:
            ServerSetting.create(key="not-a-key", value="no-no")
        assert str(exc.value) == "Server setting key 'not-a-key' is unknown"

    def test_construct(self):
        """Test server setting constructor"""
        setting = ServerSetting(key="dataset-lifetime", value="2")
        assert setting.key == "dataset-lifetime"
        assert setting.value == "2"
        assert str(setting) == "dataset-lifetime: '2'"
        self.session.check_session()

    def test_create(self):
        """Test server setting creation"""
        setting = ServerSetting.create(key="dataset-lifetime", value="2")
        assert setting.key == "dataset-lifetime"
        assert setting.value == "2"
        assert str(setting) == "dataset-lifetime: '2'"
        self.session.check_session(
            committed=[
                FakeRow(cls=ServerSetting, id=1, key="dataset-lifetime", value="2")
            ]
        )

    def test_construct_duplicate(self):
        """Test server setting constructor"""
        ServerSetting.create(key="dataset-lifetime", value=1)
        self.session.check_session(
            committed=[
                FakeRow(cls=ServerSetting, id=1, key="dataset-lifetime", value="1")
            ]
        )
        with pytest.raises(ServerSettingDuplicate) as e:
            self.session.raise_on_commit = IntegrityError(
                statement="", params="", orig=FakeDBOrig("UNIQUE constraint")
            )
            ServerSetting.create(key="dataset-lifetime", value=2)
        assert str(e).find("dataset-lifetime") != -1
        self.session.check_session(
            committed=[
                FakeRow(cls=ServerSetting, id=1, key="dataset-lifetime", value="1")
            ],
            rolledback=1,
        )

    def test_construct_null(self):
        """Test server setting constructor"""
        with pytest.raises(ServerSettingNullKey):
            self.session.raise_on_commit = IntegrityError(
                statement="", params="", orig=FakeDBOrig("NOT NULL constraint")
            )
            ServerSetting.create(key="dataset-lifetime", value=2)
        self.session.check_session(
            rolledback=1,
        )

    def test_get(self):
        """Test that we can retrieve what we set"""
        setting = ServerSetting.create(key="dataset-lifetime", value="2")
        result = ServerSetting.get(key="dataset-lifetime")
        assert setting == result
        self.session.check_session(
            committed=[
                FakeRow(cls=ServerSetting, id=1, key="dataset-lifetime", value="2")
            ],
            queries=1,
            filters=["key=dataset-lifetime"],
        )

    def test_update(self):
        """Test that we can update an existing server setting"""
        setting = ServerSetting.create(key="dataset-lifetime", value="2")
        self.session.check_session(
            committed=[
                FakeRow(cls=ServerSetting, id=1, key="dataset-lifetime", value="2")
            ]
        )
        setting.value = "5"
        setting.update()
        self.session.check_session(
            committed=[
                FakeRow(cls=ServerSetting, id=1, key="dataset-lifetime", value="5")
            ]
        )
        result = ServerSetting.get(key="dataset-lifetime")
        assert setting == result
        self.session.check_session(
            committed=[
                FakeRow(cls=ServerSetting, id=1, key="dataset-lifetime", value="5")
            ],
            queries=1,
            filters=["key=dataset-lifetime"],
        )

    def test_set(self):
        """Test that we can use set to both create and update server settings"""
        setting = ServerSetting.set(key="dataset-lifetime", value="40 days")
        result = ServerSetting.get(key="dataset-lifetime")
        assert setting == result
        assert setting.value == "40"
        ServerSetting.set(key="dataset-lifetime", value=120)
        result = ServerSetting.get(key="dataset-lifetime")
        assert result.value == "120"

        # NOTE: each `get` does a query, plus each `set` checks whether the
        # key already exists: 2 get + 2 set == 4 queries
        self.session.check_session(
            committed=[
                FakeRow(cls=ServerSetting, id=1, key="dataset-lifetime", value="120")
            ],
            queries=4,
            filters=[
                "key=dataset-lifetime",
                "key=dataset-lifetime",
                "key=dataset-lifetime",
                "key=dataset-lifetime",
            ],
        )

    def test_missing(self):
        """Check that 'create' complains about a missing key"""
        with pytest.raises(ServerSettingMissingKey):
            ServerSetting.create(key=None, value=None)

    def test_get_all_default(self):
        """
        Test get_all when no values have been set. It should return all the
        defined keys, but with None values.
        """
        assert ServerSetting.get_all() == {
            "dataset-lifetime": "3650",
            "server-state": {"status": "enabled"},
            "server-banner": None,
        }

    def test_get_all(self):
        """
        Set values and make sure they're all reported correctly
        """
        c1 = ServerSetting.create(key="dataset-lifetime", value="2")
        c2 = ServerSetting.create(key="server-state", value={"status": "enabled"})
        c3 = ServerSetting.create(key="server-banner", value={"message": "Mine"})
        assert ServerSetting.get_all() == {
            "dataset-lifetime": "2",
            "server-state": {"status": "enabled"},
            "server-banner": {"message": "Mine"},
        }
        self.session.check_session(
            queries=1,
            committed=[FakeRow.clone(c1), FakeRow.clone(c2), FakeRow.clone(c3)],
            filters=[],
        )

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
        setting = ServerSetting.create(key="dataset-lifetime", value=value)
        assert setting.value == expected

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
        with pytest.raises(ServerSettingBadValue) as exc:
            ServerSetting.create(key="dataset-lifetime", value=value)
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
        setting = ServerSetting.create(key=key, value=value)
        assert setting.key == key
        assert setting.value == value

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
        with pytest.raises(ServerSettingBadValue) as exc:
            ServerSetting.create(key="server-state", value=value)
        assert exc.value.value == value

    @pytest.mark.parametrize("value", [1, True, "yes", ["a", "b"], {"banner": "xyzzy"}])
    def test_bad_banner(self, value):
        """
        A "server-banner" value must include at least "message"
        """
        with pytest.raises(ServerSettingBadValue) as exc:
            ServerSetting.create(key="server-banner", value=value)
        assert exc.value.value == value
