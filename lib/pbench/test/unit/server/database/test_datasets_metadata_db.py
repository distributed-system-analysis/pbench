import pytest
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
        """ Various tests on Metadata keys
        """
        # See if we can create a metadata row
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        assert ds.metadatas == []
        m = Metadata.create(key="user", value=True, dataset=ds)
        assert m is not None
        assert ds.metadatas == [m]

        # Try to get it back
        m1 = Metadata.get(ds, "user")
        assert m1.key == m.key
        assert m1.value == m.value
        assert m.id == m1.id
        assert m.dataset_ref == m1.dataset_ref

        # Check the str()
        assert "test(1)|frodo|fio>>user" == str(m)

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
            Metadata(key="user")

        # Try to add a duplicate metadata key
        with pytest.raises(MetadataDuplicateKey) as exc:
            m1 = Metadata(key="user", value="IRRELEVANT")
            m1.add(ds)
        assert exc.value.key == "user"
        assert exc.value.dataset == ds
        assert ds.metadatas == [m]

        # Try to add a Metadata key to something that's not a dataset
        with pytest.raises(DatasetBadParameterType) as exc:
            m1 = Metadata(key="user", value="DONTCARE")
            m1.add("foobar")
        assert exc.value.bad_value == "foobar"
        assert exc.value.expected_type == Dataset.__name__

        # Try to create a Metadata with a bad value for the dataset
        with pytest.raises(DatasetBadParameterType) as exc:
            m1 = Metadata.create(key="user", value="TRUE", dataset=[ds])
        assert exc.value.bad_value == [ds]
        assert exc.value.expected_type == Dataset.__name__

        # Try to update the metadata key
        m.value = "False"
        m.update()
        m1 = Metadata.get(ds, "user")
        assert m.id == m1.id
        assert m.dataset_ref == m1.dataset_ref
        assert m.key == m1.key
        assert m.value == "False"

        # Delete the key and make sure its gone
        m.delete()
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, "user")
        assert exc.value.dataset == ds
        assert exc.value.key == "user"
        assert ds.metadatas == []

    def test_metadata_remove(self, db_session, create_user):
        """ Test that we can remove a Metadata key
        """
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        assert ds.metadatas == []
        m = Metadata(key="user", value="TRUE")
        m.add(ds)
        assert ds.metadatas == [m]

        Metadata.remove(ds, "user")
        assert ds.metadatas == []
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, "user")
        assert exc.value.dataset == ds
        assert exc.value.key == "user"

        Metadata.remove(ds, "user")
        assert ds.metadatas == []


class TestMetadataNamespace:
    def test_get_bad_syntax(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.getvalue(ds, "user..foo")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "user..foo"
        assert str(exc.value) == "Metadata key 'user..foo' is not supported"

    def test_set_bad_syntax(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.setvalue(ds, "user.foo.", "irrelevant")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "user.foo."
        assert str(exc.value) == "Metadata key 'user.foo.' is not supported"

    def test_set_bad_characters(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.setvalue(ds, "user.*!foo", "irrelevant")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "user.*!foo"
        assert str(exc.value) == "Metadata key 'user.*!foo' is not supported"

    def test_get_novalue(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        assert Metadata.getvalue(ds, "user.email") is None
        assert Metadata.getvalue(ds, "user") is None

    def test_get_bad_path(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        Metadata.setvalue(ds, "user.contact", "hello")
        with pytest.raises(MetadataBadStructure) as exc:
            Metadata.getvalue(ds, "user.contact.email")
        assert exc.type == MetadataBadStructure
        assert exc.value.key == "user.contact.email"
        assert exc.value.element == "contact"
        assert (
            str(exc.value)
            == "Key 'contact' value for 'user.contact.email' in test(1)|frodo|fio is not a JSON object"
        )

    def test_set_bad_path(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        Metadata.setvalue(ds, "user.contact", "hello")
        with pytest.raises(MetadataBadStructure) as exc:
            Metadata.setvalue(ds, "user.contact.email", "me@example.com")
        assert exc.type == MetadataBadStructure
        assert exc.value.key == "user.contact.email"
        assert exc.value.element == "contact"
        assert (
            str(exc.value)
            == "Key 'contact' value for 'user.contact.email' in test(1)|frodo|fio is not a JSON object"
        )

    def test_get_outer_path(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        Metadata.setvalue(ds, "user.value.hello.english", "hello")
        Metadata.setvalue(ds, "user.value.hello.espanol", "hola")
        assert Metadata.getvalue(ds, "user.value") == {
            "hello": {"english": "hello", "espanol": "hola"}
        }

    def test_get_inner_path(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        Metadata.setvalue(
            ds,
            "user.contact",
            {"email": "me@example.com", "name": {"first": "My", "last": "Name"}},
        )
        assert Metadata.getvalue(ds, "user.contact.email") == "me@example.com"
        assert Metadata.getvalue(ds, "user.contact.name.first") == "My"
        assert Metadata.getvalue(ds, "user.contact.name") == {
            "first": "My",
            "last": "Name",
        }

    def test_delete_with_metadata(self, db_session, create_user):
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        Metadata.setvalue(
            ds,
            "user.contact",
            {"email": "me@example.com", "name": {"first": "My", "last": "Name"}},
        )
        assert Metadata.getvalue(ds, "user.contact.email") == "me@example.com"
        assert Metadata.getvalue(ds, "user.contact.name.first") == "My"
        assert Metadata.getvalue(ds, "user.contact.name") == {
            "first": "My",
            "last": "Name",
        }
        ds.delete()

        with pytest.raises(DatasetNotFound):
            Dataset.query(name="fio")
