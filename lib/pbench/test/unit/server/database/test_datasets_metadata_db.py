import pytest
from sqlalchemy import or_

from pbench.server.database.database import Database
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetNotFound,
    Metadata,
    DatasetBadParameterType,
    MetadataBadStructure,
    MetadataNotFound,
    MetadataBadKey,
    MetadataMissingKeyValue,
    MetadataDuplicateKey,
)


class TestMetadata:
    def test_metadata(self, db_session, create_user):
        """Various tests on Metadata keys"""
        # See if we can create a metadata row
        ds = Dataset.create(owner=create_user.username, name="fio")
        assert ds.metadatas == []
        m = Metadata.create(key="dashboard", value=True, dataset=ds)
        assert m is not None
        assert ds.metadatas == [m]

        # Try to get it back
        m1 = Metadata.get(ds, "dashboard")
        assert m1.key == m.key
        assert m1.value == m.value
        assert m.id == m1.id
        assert m.dataset_ref == m1.dataset_ref

        # Check the str()
        assert "test(1)|fio>>dashboard" == str(m)

        # Try to get a metadata key that doesn't exist
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, "no key")
        assert exc.value.dataset == ds
        assert exc.value.key == "no key"

        # Try to remove a metadata key that doesn't exist (No-op)
        Metadata.remove(ds, "no key")

        # Try to create a metadata with a bad key
        badkey = "THISISNOTTHEKEYYOURELOOKINGFOR"
        with pytest.raises(MetadataBadKey) as exc:
            Metadata(key=badkey, value=None)
        assert exc.value.key == badkey

        # Try to create a key without a value
        with pytest.raises(MetadataMissingKeyValue):
            Metadata(key="dashboard")

        # Try to add a duplicate metadata key
        with pytest.raises(MetadataDuplicateKey) as exc:
            m1 = Metadata(key="dashboard", value="IRRELEVANT")
            m1.add(ds)
        assert exc.value.key == "dashboard"
        assert exc.value.dataset == ds
        assert ds.metadatas == [m]

        # Try to add a Metadata key to something that's not a dataset
        with pytest.raises(DatasetBadParameterType) as exc:
            m1 = Metadata(key="dashboard", value="DONTCARE")
            m1.add("foobar")
        assert exc.value.bad_value == "foobar"
        assert exc.value.expected_type == Dataset.__name__

        # Try to create a Metadata with a bad value for the dataset
        with pytest.raises(DatasetBadParameterType) as exc:
            m1 = Metadata.create(key="dashboard", value="TRUE", dataset=[ds])
        assert exc.value.bad_value == [ds]
        assert exc.value.expected_type == Dataset.__name__

        # Try to update the metadata key
        m.value = "False"
        m.update()
        m1 = Metadata.get(ds, "dashboard")
        assert m.id == m1.id
        assert m.dataset_ref == m1.dataset_ref
        assert m.key == m1.key
        assert m.value == "False"

        # Delete the key and make sure its gone
        m.delete()
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, "dashboard")
        assert exc.value.dataset == ds
        assert exc.value.key == "dashboard"
        assert ds.metadatas == []

    def test_metadata_remove(self, db_session, create_user):
        """Test that we can remove a Metadata key"""
        ds = Dataset.create(owner=create_user.username, name="fio")
        assert ds.metadatas == []
        m = Metadata(key="dashboard", value="TRUE")
        m.add(ds)
        assert ds.metadatas == [m]

        Metadata.remove(ds, "dashboard")
        assert ds.metadatas == []
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, "dashboard")
        assert exc.value.dataset == ds
        assert exc.value.key == "dashboard"

        Metadata.remove(ds, "dashboard")
        assert ds.metadatas == []


class TestMetadataNamespace:
    def test_get_bad_syntax(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, name="fio")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.getvalue(ds, "dashboard..foo")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "dashboard..foo"
        assert str(exc.value) == "Metadata key 'dashboard..foo' is not supported"

    def test_user_metadata(self, db_session, create_user, create_drb_user):
        """Various tests on user-mapped Metadata keys"""
        # See if we can create a metadata row
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        assert ds.metadatas == []
        t = Metadata.create(key="user", value=True, dataset=ds, user=create_user)
        assert t is not None
        assert ds.metadatas == [t]
        assert create_user.dataset_metadata == [t]

        d = Metadata.create(key="user", value=False, dataset=ds, user=create_drb_user)
        assert d is not None
        assert ds.metadatas == [t, d]
        assert create_user.dataset_metadata == [t]
        assert create_drb_user.dataset_metadata == [d]

        g = Metadata.create(key="user", value="text", dataset=ds)
        assert g is not None
        assert ds.metadatas == [t, d, g]
        assert create_user.dataset_metadata == [t]
        assert create_drb_user.dataset_metadata == [d]

        assert Metadata.get(key="user", dataset=ds).value == "text"
        assert Metadata.get(key="user", dataset=ds, user=create_user).value is True
        assert Metadata.get(key="user", dataset=ds, user=create_drb_user).value is False

        Metadata.remove(key="user", dataset=ds, user=create_drb_user)
        assert create_drb_user.dataset_metadata == []
        assert create_user.dataset_metadata == [t]
        assert ds.metadatas == [t, g]

        Metadata.remove(key="user", dataset=ds)
        assert create_user.dataset_metadata == [t]
        assert ds.metadatas == [t]

        Metadata.remove(key="user", dataset=ds, user=create_user)
        assert create_user.dataset_metadata == []
        assert ds.metadatas == []

        # Peek under the carpet to look for orphaned metadata objects linked
        # to the Dataset or User
        metadata = (
            Database.db_session.query(Metadata).filter_by(dataset_ref=ds.id).first()
        )
        assert metadata is None
        metadata = (
            Database.db_session.query(Metadata)
            .filter(
                or_(
                    Metadata.user_ref == create_drb_user.id,
                    Metadata.user_ref == create_user.id,
                    Metadata.user_ref is None,
                )
            )
            .first()
        )
        assert metadata is None

    def test_set_bad_syntax(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, name="fio")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.setvalue(ds, "dashboard.foo.", "irrelevant")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "dashboard.foo."
        assert str(exc.value) == "Metadata key 'dashboard.foo.' is not supported"

    def test_set_bad_characters(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, name="fio")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.setvalue(ds, "dashboard.*!foo", "irrelevant")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "dashboard.*!foo"
        assert str(exc.value) == "Metadata key 'dashboard.*!foo' is not supported"

    def test_get_novalue(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, name="fio")
        assert Metadata.getvalue(ds, "dashboard.email") is None
        assert Metadata.getvalue(ds, "dashboard") is None

    def test_get_bad_path(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, name="fio")
        Metadata.setvalue(ds, "dashboard.contact", "hello")
        with pytest.raises(MetadataBadStructure) as exc:
            Metadata.getvalue(ds, "dashboard.contact.email")
        assert exc.type == MetadataBadStructure
        assert exc.value.key == "dashboard.contact.email"
        assert exc.value.element == "contact"
        assert (
            str(exc.value)
            == "Key 'contact' value for 'dashboard.contact.email' in test(1)|frodo|fio is not a JSON object"
        )

    def test_set_bad_path(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, name="fio")
        Metadata.setvalue(ds, "dashboard.contact", "hello")
        with pytest.raises(MetadataBadStructure) as exc:
            Metadata.setvalue(ds, "dashboard.contact.email", "me@example.com")
        assert exc.type == MetadataBadStructure
        assert exc.value.key == "dashboard.contact.email"
        assert exc.value.element == "contact"
        assert (
            str(exc.value)
            == "Key 'contact' value for 'dashboard.contact.email' in test(1)|frodo|fio is not a JSON object"
        )

    def test_get_outer_path(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        Metadata.setvalue(ds, "dashboard.value.hello.english", "hello")
        Metadata.setvalue(ds, "dashboard.value.hello.espanol", "hola")
        assert Metadata.getvalue(ds, "dashboard.value") == {
            "hello": {"english": "hello", "espanol": "hola"}
        }

    def test_get_inner_path(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, name="fio")
        Metadata.setvalue(
            ds,
            "dashboard.contact",
            {"email": "me@example.com", "name": {"first": "My", "last": "Name"}},
        )
        assert Metadata.getvalue(ds, "dashboard.contact.email") == "me@example.com"
        assert Metadata.getvalue(ds, "dashboard.contact.name.first") == "My"
        assert Metadata.getvalue(ds, "dashboard.contact.name") == {
            "first": "My",
            "last": "Name",
        }

    def test_delete_with_metadata(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, name="fio")
        Metadata.setvalue(
            ds,
            "dashboard.contact",
            {"email": "me@example.com", "name": {"first": "My", "last": "Name"}},
        )
        assert Metadata.getvalue(ds, "dashboard.contact.email") == "me@example.com"
        assert Metadata.getvalue(ds, "dashboard.contact.name.first") == "My"
        assert Metadata.getvalue(ds, "dashboard.contact.name") == {
            "first": "My",
            "last": "Name",
        }
        id = ds.id
        ds.delete()

        # Test that the dataset is gone by searching for it
        with pytest.raises(DatasetNotFound):
            Dataset.query(name="fio")

        # Peek under the carpet to look for orphaned metadata objects linked
        # to the deleted Dataset
        metadata = Database.db_session.query(Metadata).filter_by(dataset_ref=id).first()
        assert metadata is None

    def test_setgetvalue_user(self, db_session, create_user, create_drb_user):
        """
        Verify that we can set and read independent values of "user." namespace
        keys across two separate users plus a "non-owned" version (user None)
        which is not supported by the current higher level access through the
        server APIs. (In other words, the "user" SQL column can be None, as we
        use this column only for the "user" key value.)
        """
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        Metadata.setvalue(dataset=ds, key="user.contact", value="Barney")
        Metadata.setvalue(
            dataset=ds, key="user.contact", value="Fred", user=create_user
        )
        Metadata.setvalue(
            dataset=ds, key="user.contact", value="Wilma", user=create_drb_user
        )

        assert Metadata.getvalue(dataset=ds, user=None, key="user") == {
            "contact": "Barney"
        }
        assert Metadata.getvalue(dataset=ds, user=create_user, key="user") == {
            "contact": "Fred"
        }
        assert Metadata.getvalue(dataset=ds, user=create_drb_user, key="user") == {
            "contact": "Wilma"
        }
