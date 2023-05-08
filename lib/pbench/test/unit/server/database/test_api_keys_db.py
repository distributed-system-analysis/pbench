import pytest

from pbench.server.database.database import Database
from pbench.server.database.models.api_keys import APIKey
from pbench.test.unit.server.database import FakeSession


class TestAPIKeyDB:

    session = None

    @pytest.fixture()
    def fake_db(self, monkeypatch, server_config):
        """
        Fixture to mock a DB session for testing.

        We patch the SQLAlchemy db_session to our fake session. We also store a
        server configuration object directly on the Database.Base (normally
        done during DB initialization) because that can't be monkeypatched.
        """
        __class__.session = FakeSession(APIKey)
        monkeypatch.setattr(Database, "db_session", __class__.session)
        Database.Base.config = server_config
        yield monkeypatch

    def test_construct(self, db_session, create_drb_user, create_user):
        """Test api_key constructor"""

        api_key = APIKey(key="generated_api_key", user=create_user, name="test_api_key")
        api_key.add()

        assert api_key.key == "generated_api_key"
        assert api_key.user.id is create_user.id
        assert api_key.name == "test_api_key"

    def test_query(
        self,
        db_session,
        pbench_drb_api_key,
        pbench_drb_secondary_api_key,
        create_drb_user,
    ):
        """Test that we are able to query api_key by user"""

        key_list = APIKey.query(user=create_drb_user)
        assert len(key_list) == 2

        assert key_list[0].user.id == pbench_drb_api_key.user.id
        assert key_list[0].name == pbench_drb_api_key.name
        assert key_list[0].id == pbench_drb_api_key.id
        assert key_list[0].key == pbench_drb_api_key.key
        assert key_list[1].user.id == pbench_drb_secondary_api_key.user.id
        assert key_list[1].name == pbench_drb_secondary_api_key.name
        assert key_list[1].id == pbench_drb_secondary_api_key.id
        assert key_list[1].key == pbench_drb_secondary_api_key.key

    def test_delete(self, db_session, pbench_drb_api_key, pbench_drb_secondary_api_key):
        """Test that we can delete an api_key"""

        # we can find it
        keys = APIKey.query(id=pbench_drb_api_key.id)
        key = keys[0]
        assert key.key == pbench_drb_api_key.key

        key.delete()
        assert APIKey.query(id=pbench_drb_api_key.id) == []

        keys = APIKey.query(id=pbench_drb_secondary_api_key.id)
        assert keys[0].key == pbench_drb_secondary_api_key.key
