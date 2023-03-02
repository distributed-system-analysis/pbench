import datetime

import pytest

from pbench.server.database.database import Database
from pbench.server.database.models.api_key import APIKey
from pbench.test.unit.server.database import FakeSession


class TestAPIKey:

    session = None

    # Current time to encode in the payload
    current_utc = datetime.datetime.now(datetime.timezone.utc)
    expiration = current_utc + datetime.timedelta(minutes=10)

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

    def test_construct(self, fake_db, create_drb_user):
        """Test api_key constructor"""

        api_key = APIKey(
            api_key="generated_api_key",
            created=self.current_utc,
            expiration=self.expiration,
        )

        assert api_key.api_key == "generated_api_key"
        assert api_key.created is self.current_utc
        assert api_key.expiration is self.expiration
        self.session.check_session()

    def test_query(self, db_session, pbench_drb_api_key):
        """Test that we can able to query api_key in the table"""

        key, created_timestamp = pbench_drb_api_key

        key2 = APIKey.query(key)
        assert key2.api_key == key

    def test_delete(self, db_session, create_user, pbench_drb_api_key):
        """Test that we can delete an api_key"""

        key, created_timestamp = pbench_drb_api_key

        # we can find it
        key2 = APIKey.query(key)
        assert key2.api_key == key

        APIKey.delete(key)
        assert APIKey.query(key) is None
