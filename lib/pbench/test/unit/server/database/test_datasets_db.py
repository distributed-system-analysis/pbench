from freezegun.api import freeze_time
import pytest

from pbench.server.database.models.datasets import Dataset, DatasetNotFound
from pbench.server.database.models.users import User
from pbench.test.unit.server import DRB_USER_ID


class TestDatasets:
    def test_construct(self, db_session, create_user):
        """Test dataset contructor"""
        user = create_user
        with freeze_time("1970-01-01"):
            ds = Dataset(owner_id=str(user.id), name="fio", resource_id="f00b0ad")
            ds.add()
        assert ds.owner_id == str(user.id)
        assert ds.name == "fio"
        assert ds.resource_id == "f00b0ad"
        assert ds.id is not None
        assert f"({user.id})|fio" == str(ds)
        assert ds.as_dict() == {
            "access": "private",
            "name": "fio",
            "owner_id": str(user.id),
            "uploaded": "1970-01-01T00:00:00+00:00",
            "metalog": None,
            "operations": {},
        }

    def test_dataset_survives_user(self, db_session, create_user):
        """The Dataset isn't automatically removed when the referenced
        user is removed.
        """
        user = create_user
        ds = Dataset(owner_id=str(user.id), name="fio", resource_id="deadbeef")
        ds.add()
        User.delete(username=user.username)
        ds1 = Dataset.query(resource_id="deadbeef")
        assert ds1 == ds

    def test_dataset_metadata_log(self, db_session, create_user, provide_metadata):
        """
        Test that `as_dict` provides the mocked metadata.log contents along
        with the Dataset object.
        """
        ds1 = Dataset.query(name="drb")
        assert ds1.as_dict() == {
            "access": "private",
            "name": "drb",
            "owner_id": DRB_USER_ID,
            "uploaded": "2022-01-01T00:00:00+00:00",
            "metalog": {
                "pbench": {
                    "config": "test1",
                    "date": "2020-02-15T00:00:00",
                    "name": "drb",
                    "script": "unit-test",
                },
                "run": {"controller": "node1.example.com"},
            },
            "operations": {},
        }

    def test_query_name(self, db_session, create_user):
        """Test that we can find a dataset by name alone"""
        ds1 = Dataset(owner_id=str(create_user.id), resource_id="deed1e", name="fio")
        ds1.add()

        ds2 = Dataset.query(name="fio")
        assert ds2.name == "fio"
        assert ds2.owner_id == ds1.owner_id
        assert ds2.name == ds1.name
        assert ds2.resource_id == ds1.resource_id
        assert ds2.id == ds1.id

    def test_delete(self, db_session, create_user):
        """Test that we can delete a dataset"""
        ds1 = Dataset(
            owner_id=str(create_user.id), name="foobar", resource_id="f00dea7"
        )
        ds1.add()

        # we can find it
        ds2 = Dataset.query(resource_id=ds1.resource_id)
        assert ds2.name == ds1.name

        ds2.delete()

        with pytest.raises(DatasetNotFound):
            Dataset.query(resource_id=ds1.resource_id)
