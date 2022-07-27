import pytest

from pbench.server.database.models.server_config import (
    ServerConfig,
    ServerConfigBadKey,
    ServerConfigBadValue,
    ServerConfigDuplicate,
    ServerConfigMissingKey,
)


class TestServerConfig:
    def test_bad_key(self, db_session):
        """Test server config parameter key validation"""
        with pytest.raises(ServerConfigBadKey) as exc:
            ServerConfig.create(key="not-a-key", value="no-no")
        assert str(exc.value) == "Configuration key 'not-a-key' is unknown"

    def test_construct(self, db_session):
        """Test server config parameter constructor"""
        config = ServerConfig(key="dataset-lifetime", value="2")
        assert config.key == "dataset-lifetime"
        assert config.value == "2"
        assert str(config) == "dataset-lifetime: '2'"

    def test_create(self, db_session):
        """Test server config parameter creation"""
        config = ServerConfig.create(key="dataset-lifetime", value="2")
        assert config.key == "dataset-lifetime"
        assert config.value == "2"
        assert str(config) == "dataset-lifetime: '2'"

    def test_construct_duplicate(self, db_session):
        """Test server config parameter constructor"""
        ServerConfig.create(key="dataset-lifetime", value=1)
        with pytest.raises(ServerConfigDuplicate) as e:
            ServerConfig.create(key="dataset-lifetime", value=2)
        assert str(e).find("dataset-lifetime") != -1

    def test_get(self, db_session):
        """Test that we can retrieve what we set"""
        config = ServerConfig.create(key="dataset-lifetime", value="2")
        result = ServerConfig.get(key="dataset-lifetime")
        assert config == result

    def test_update(self, db_session):
        config = ServerConfig.create(key="dataset-lifetime", value="2")
        config.value = "5"
        config.update()
        result = ServerConfig.get(key="dataset-lifetime")
        assert config == result

    def test_set(self, db_session):
        config = ServerConfig.set(key="dataset-lifetime", value="40 days")
        result = ServerConfig.get(key="dataset-lifetime")
        assert config == result
        assert config.value == "40"
        ServerConfig.set(key="dataset-lifetime", value=120)
        result = ServerConfig.get(key="dataset-lifetime")
        assert result.value == "120"

    def test_missing(self, db_session):
        with pytest.raises(ServerConfigMissingKey):
            ServerConfig.create(key=None, value=None)

    def test_get_all_default(self, db_session):
        """
        Test get_all when no values have been set. It should return all the
        defined keys, but with None values.
        """
        assert ServerConfig.get_all() == {
            "dataset-lifetime": "3650",
            "server-state": {"status": "enabled"},
            "server-banner": None,
        }

    def test_get_all(self, db_session):
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
    def test_lifetimes(self, db_session, value, expected):
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
    def test_bad_lifetimes(self, db_session, value):
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
    def test_create_state_and_banner(self, db_session, key, value):
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
    def test_bad_state(self, db_session, value):
        """
        A "server-state" value must include at least "status" and if the value
        isn't "enabled" must also contain "message"
        """
        with pytest.raises(ServerConfigBadValue) as exc:
            ServerConfig.create(key="server-state", value=value)
        assert exc.value.value == value

    @pytest.mark.parametrize("value", [1, True, "yes", ["a", "b"], {"banner": "xyzzy"}])
    def test_bad_banner(self, db_session, value):
        """
        A "server-banner" value must include at least "message"
        """
        with pytest.raises(ServerConfigBadValue) as exc:
            ServerConfig.create(key="server-banner", value=value)
        assert exc.value.value == value
