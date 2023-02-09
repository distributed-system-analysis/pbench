import pytest
from sqlalchemy import or_

from pbench.server.database.database import Database
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetBadParameterType,
    DatasetNotFound,
    Metadata,
    MetadataBadKey,
    MetadataBadStructure,
    MetadataBadValue,
    MetadataDuplicateKey,
    MetadataMissingKeyValue,
    MetadataNotFound,
)
from pbench.server.database.models.users import User


class TestGetSetMetadata:
    def test_metadata(self, more_datasets):
        """Various tests on Metadata keys"""
        # See if we can create a metadata row
        ds = Dataset.query(name="drb")
        assert ds.metadatas == []
        m = Metadata.create(key="global", value=True, dataset=ds)
        assert m is not None
        assert ds.metadatas == [m]

        # Try to get it back
        m1 = Metadata.get(ds, "global")
        assert m1.key == m.key
        assert m1.value == m.value
        assert m.id == m1.id
        assert m.dataset_ref == m1.dataset_ref

        # Check the str()
        assert "(3)|drb>>global" == str(m)

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
            Metadata(key="global")

        # Try to add a duplicate metadata key
        with pytest.raises(MetadataDuplicateKey) as exc:
            m1 = Metadata(key="global", value="IRRELEVANT")
            m1.add(ds)
        assert exc.value.key == "global"
        assert exc.value.dataset == ds
        assert ds.metadatas == [m], f"Keys {[m.key for m in ds.metadatas]} remain"

        # Try to add a Metadata key to something that's not a dataset
        with pytest.raises(DatasetBadParameterType) as exc:
            m1 = Metadata(key="global", value="DONTCARE")
            m1.add("foobar")
        assert exc.value.bad_value == "foobar"
        assert exc.value.expected_type == Dataset.__name__

        # Try to create a Metadata with a bad value for the dataset
        with pytest.raises(DatasetBadParameterType) as exc:
            m1 = Metadata.create(key="global", value="TRUE", dataset=[ds])
        assert exc.value.bad_value == [ds]
        assert exc.value.expected_type == Dataset.__name__

        # Try to update the metadata key
        m.value = "False"
        m.update()
        m1 = Metadata.get(ds, "global")
        assert m.id == m1.id
        assert m.dataset_ref == m1.dataset_ref
        assert m.key == m1.key
        assert m.value == "False"

        # Delete the key and make sure its gone
        m.delete()
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, "global")
        assert exc.value.dataset == ds
        assert exc.value.key == "global"
        assert ds.metadatas == [], f"Keys {[m.key for m in ds.metadatas]} remain"

    def test_metadata_remove(self, attach_dataset):
        """Test that we can remove a Metadata key"""
        ds = Dataset.query(name="test")
        assert ds.metadatas == []
        m = Metadata(key="global", value="TRUE")
        m.add(ds)
        assert ds.metadatas == [m]

        Metadata.remove(ds, "global")
        assert ds.metadatas == []
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, "global")
        assert exc.value.dataset == ds
        assert exc.value.key == "global"

        Metadata.remove(ds, "global")
        assert ds.metadatas == []


class TestInternalMetadata:
    def test_dataset_full(self, provide_metadata, create_drb_user):
        ds = Dataset.query(name="drb")
        metadata = Metadata.getvalue(ds, "dataset")
        assert metadata == {
            "access": "private",
            "name": "drb",
            "owner_id": str(create_drb_user.id),
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

    def test_dataset_keys(self, provide_metadata):
        ds = Dataset.query(name="drb")
        metadata = Metadata.getvalue(ds, "dataset.metalog.run")
        assert metadata == {"controller": "node1.example.com"}
        metadata = Metadata.getvalue(ds, "dataset.metalog.pbench.name")
        assert metadata == "drb"
        metadata = Metadata.getvalue(ds, "dataset.nosuchkey")
        assert metadata is None

    def test_server_full(self, provide_metadata):
        ds = Dataset.query(name="drb")
        metadata = Metadata.getvalue(ds, "server")
        assert metadata == {
            "deletion": "2022-12-26",
            "index-map": {
                "unit-test.v6.run-data.2020-08": ["random_md5_string1"],
                "unit-test.v5.result-data-sample.2020-08": ["random_document_uuid"],
                "unit-test.v6.run-toc.2020-05": ["random_md5_string1"],
            },
        }

    def test_server_keys(self, provide_metadata):
        ds = Dataset.query(name="drb")
        metadata = Metadata.getvalue(ds, "server.deletion")
        assert metadata == "2022-12-26"
        metadata = Metadata.getvalue(ds, "server.index-map")
        assert metadata == {
            "unit-test.v6.run-data.2020-08": ["random_md5_string1"],
            "unit-test.v5.result-data-sample.2020-08": ["random_document_uuid"],
            "unit-test.v6.run-toc.2020-05": ["random_md5_string1"],
        }
        metadata = Metadata.getvalue(ds, "server.webbwantsthistest")
        assert metadata is None


class TestMetadataNamespace:
    def test_get_bad_syntax(self, attach_dataset):
        ds = Dataset.query(name="drb")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.getvalue(ds, "global..foo")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "global..foo"
        assert str(exc.value) == "Metadata key 'global..foo' is not supported"

    def test_user_metadata(self, attach_dataset):
        """Various tests on user-mapped Metadata keys"""
        # See if we can create a metadata row
        ds = Dataset.query(name="drb")
        user1 = str(User.query(username="drb").id)
        metadata_db_query = Database.db_session.query(Metadata)
        assert ds.metadatas == []
        t = Metadata.create(key="user", value=True, dataset=ds, user_id=user1)
        assert t is not None
        assert ds.metadatas == [t]
        assert Database.db_session.query(Metadata).filter_by(user_id=user1).all() == [t]

        user2 = str(User.query(username="test").id)
        d = Metadata.create(key="user", value=False, dataset=ds, user_id=user2)
        assert d is not None
        assert ds.metadatas == [t, d]
        assert metadata_db_query.filter_by(user_id=user1).all() == [t]
        assert metadata_db_query.filter_by(user_id=user2).all() == [d]

        g = Metadata.create(key="user", value="text", dataset=ds)
        assert g is not None
        assert ds.metadatas == [t, d, g]
        assert metadata_db_query.filter_by(user_id=user1).all() == [t]
        assert metadata_db_query.filter_by(user_id=user2).all() == [d]

        assert Metadata.get(key="user", dataset=ds).value == "text"
        assert Metadata.get(key="user", dataset=ds, user_id=user1).value is True
        assert Metadata.get(key="user", dataset=ds, user_id=user2).value is False

        Metadata.remove(key="user", dataset=ds, user_id=user1)
        assert metadata_db_query.filter_by(user_id=user1).all() == []
        assert metadata_db_query.filter_by(user_id=user2).all() == [d]
        assert ds.metadatas == [d, g]

        Metadata.remove(key="user", dataset=ds)
        assert metadata_db_query.filter_by(user_id=user1).all() == []
        assert metadata_db_query.filter_by(user_id=user2).all() == [d]
        assert ds.metadatas == [d]

        Metadata.remove(key="user", dataset=ds, user_id=user2)
        assert metadata_db_query.filter_by(user_id=user1).all() == []
        assert metadata_db_query.filter_by(user_id=user2).all() == []
        assert ds.metadatas == []

        # Peek under the carpet to look for orphaned metadata objects linked
        # to the Dataset or User
        metadata = metadata_db_query.filter_by(dataset_ref=ds.id).first()
        assert metadata is None
        metadata = metadata_db_query.filter(
            or_(
                Metadata.user_id == user1,
                Metadata.user_id == user2,
                Metadata.user_id is None,
            )
        ).first()
        assert metadata is None

    def test_set_bad_syntax(self, attach_dataset):
        ds = Dataset.query(name="drb")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.setvalue(ds, "global.foo.", "irrelevant")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "global.foo."
        assert str(exc.value) == "Metadata key 'global.foo.' is not supported"

    def test_set_bad_characters(self, attach_dataset):
        ds = Dataset.query(name="drb")
        with pytest.raises(MetadataBadKey) as exc:
            Metadata.setvalue(ds, "global.*!foo", "irrelevant")
        assert exc.type == MetadataBadKey
        assert exc.value.key == "global.*!foo"
        assert str(exc.value) == "Metadata key 'global.*!foo' is not supported"

    def test_get_novalue(self, attach_dataset):
        ds = Dataset.query(name="drb")
        assert Metadata.getvalue(ds, "global.email") is None
        assert Metadata.getvalue(ds, "global") is None

    def test_get_bad_path(self, attach_dataset):
        ds = Dataset.query(name="drb")
        Metadata.setvalue(ds, "global.contact", "hello")
        with pytest.raises(MetadataBadStructure) as exc:
            Metadata.getvalue(ds, "global.contact.email")
        assert exc.type == MetadataBadStructure
        assert exc.value.key == "global.contact.email"
        assert exc.value.element == "contact"
        assert (
            str(exc.value)
            == "Key 'contact' value for 'global.contact.email' in (3)|drb is not a JSON object"
        )

    def test_set_bad_path(self, attach_dataset):
        ds = Dataset.query(name="drb")
        Metadata.setvalue(ds, "global.contact", "hello")
        with pytest.raises(MetadataBadStructure) as exc:
            Metadata.setvalue(ds, "global.contact.email", "me@example.com")
        assert exc.type == MetadataBadStructure
        assert exc.value.key == "global.contact.email"
        assert exc.value.element == "contact"
        assert (
            str(exc.value)
            == "Key 'contact' value for 'global.contact.email' in (3)|drb is not a JSON object"
        )

    def test_get_outer_path(self, attach_dataset):
        ds = Dataset.query(name="drb")
        Metadata.setvalue(ds, "global.value.hello.english", "hello")
        Metadata.setvalue(ds, "global.value.hello.espanol", "hola")
        assert Metadata.getvalue(ds, "global.value") == {
            "hello": {"english": "hello", "espanol": "hola"}
        }

    def test_get_inner_path(self, attach_dataset):
        ds = Dataset.query(name="drb")
        Metadata.setvalue(
            ds,
            "global.contact",
            {"email": "me@example.com", "name": {"first": "My", "last": "Name"}},
        )
        assert Metadata.getvalue(ds, "global.contact.email") == "me@example.com"
        assert Metadata.getvalue(ds, "global.contact.name.first") == "My"
        assert Metadata.getvalue(ds, "global.contact.name") == {
            "first": "My",
            "last": "Name",
        }

    def test_delete_with_metadata(self, attach_dataset):
        ds = Dataset.query(name="drb")
        Metadata.setvalue(
            ds,
            "global.contact",
            {"email": "me@example.com", "name": {"first": "My", "last": "Name"}},
        )
        assert Metadata.getvalue(ds, "global.contact.email") == "me@example.com"
        assert Metadata.getvalue(ds, "global.contact.name.first") == "My"
        assert Metadata.getvalue(ds, "global.contact.name") == {
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

    def test_setgetvalue_user(self, attach_dataset):
        """
        Verify that we can set and read independent values of "user." namespace
        keys across two separate users plus a "non-owned" version (user None)
        which is not supported by the current higher level access through the
        server APIs. (In other words, the "user" SQL column can be None, as we
        use this column only for the "user" key value.)
        """
        ds = Dataset.query(name="drb")
        user1 = str(User.query(username="drb").id)
        user2 = str(User.query(username="test").id)
        Metadata.setvalue(dataset=ds, key="user.contact", value="Barney")
        Metadata.setvalue(dataset=ds, key="user.contact", value="Fred", user_id=user2)
        Metadata.setvalue(dataset=ds, key="user.contact", value="Wilma", user_id=user1)

        assert Metadata.getvalue(dataset=ds, user_id=None, key="user") == {
            "contact": "Barney"
        }
        assert Metadata.getvalue(dataset=ds, user_id=user2, key="user") == {
            "contact": "Fred"
        }
        assert Metadata.getvalue(dataset=ds, user_id=user1, key="user") == {
            "contact": "Wilma"
        }

    @pytest.mark.parametrize(
        "value",
        [
            "Symbols like $ and _ and @",
            "MY_DATA_IS_UGLY",
            "1234567890",
            "La palabra año incluye unicode",
            "Shift to the left",
            "1",
            "X" * 1024,
        ],
    )
    def test_mutable_dataset(self, attach_dataset, value):
        """
        Try setting a few valid names.
        """
        ds = Dataset.query(name="drb")
        Metadata.setvalue(ds, "dataset.name", value)
        assert Metadata.getvalue(ds, "dataset")["name"] == value

    @pytest.mark.parametrize("value", ["", True, 1, ""])
    def test_mutable_dataset_bad(self, attach_dataset, value):
        """
        Test the reaction to a "bad" string name.

        NOTE: we don't try to test a string that's "too long" as in the sqlite3
        database we use for unit testing, where `varchar` isn't enforced, we'd
        need to create a billion character string.
        """
        ds = Dataset.query(name="drb")
        name = ds.name
        with pytest.raises(MetadataBadValue) as exc:
            Metadata.setvalue(ds, "dataset.name", value)
        assert (
            str(exc.value)
            == f"Metadata key 'dataset.name' value {value!r} for dataset (3)|drb must be a UTF-8 string of 1 to 1024 characters"
        )
        assert Metadata.getvalue(ds, "dataset.name") == name

    def test_mutable_server(self, server_config, attach_dataset):
        """
        Set the dataset deletion time to a valid date/time string
        """
        ds = Dataset.query(name="drb")
        Metadata.setvalue(ds, "server.deletion", "1979-12-29 08:00-04:00")
        assert Metadata.getvalue(ds, "server.deletion") == "1979-12-30"

    @pytest.mark.parametrize(
        "value,message",
        [
            (
                "Not a date",
                "Metadata key 'server.deletion' value 'Not a date' for dataset (3)|drb must be a date/time",
            ),
            (
                "2040-12-25",
                "Metadata key 'server.deletion' value '2040-12-25' for dataset (3)|drb must be a date/time before 2031-12-30",
            ),
        ],
    )
    def test_mutable_server_bad(self, server_config, attach_dataset, value, message):
        """
        Try out some invalid deletion time values.

        The value must be a valid date/time string, and it must be within the
        server's maximum retention threshold from the dataset's upload time.
        """
        ds = Dataset.query(name="drb")
        deletion = Metadata.getvalue(ds, "server.deletion")
        with pytest.raises(MetadataBadValue) as exc:
            Metadata.setvalue(ds, "server.deletion", value)
        assert str(exc.value) == message
        assert Metadata.getvalue(ds, "server.deletion") == deletion

    def test_mutable_origin(self, server_config, attach_dataset):
        """
        Set the dataset origin origin metadata
        """
        ds = Dataset.query(name="drb")
        Metadata.setvalue(ds, "server.origin", "RIYA")
        assert Metadata.getvalue(ds, "server.origin") == "RIYA"

    @pytest.mark.parametrize(
        "value,message",
        [
            (
                True,
                "Metadata key 'server.origin' value True for dataset (3)|drb must be a string",
            ),
            (
                [],
                "Metadata key 'server.origin' value [] for dataset (3)|drb must be a string",
            ),
            (
                1,
                "Metadata key 'server.origin' value 1 for dataset (3)|drb must be a string",
            ),
        ],
    )
    def test_mutable_origin_bad(self, server_config, attach_dataset, value, message):
        """
        Try out some invalid deletion time values.

        The value must be a valid date/time string, and it must be within the
        server's maximum retention threshold from the dataset's upload time.
        """
        ds = Dataset.query(name="drb")
        with pytest.raises(MetadataBadValue) as exc:
            Metadata.setvalue(ds, "server.origin", value)
        assert str(exc.value) == message
        assert Metadata.getvalue(ds, "server.origin") is None

    @pytest.mark.parametrize(
        "value,result",
        [
            ("true", True),
            ("false", False),
            ("t", True),
            ("f", False),
            ("y", True),
            ("yEs", True),
            ("n", False),
            ("No", False),
            (1, True),
            (0, False),
            ("True", True),
            ("FAlSe", False),
        ],
    )
    def test_mutable_archiveonly(self, server_config, attach_dataset, value, result):
        """
        Try out some invalid deletion time values.

        The value must be a valid date/time string, and it must be within the
        server's maximum retention threshold from the dataset's upload time.
        """
        ds = Dataset.query(name="drb")
        Metadata.setvalue(ds, "server.archiveonly", value)
        assert Metadata.getvalue(ds, "server.archiveonly") == result

    @pytest.mark.parametrize(
        "value,message",
        [
            (
                "ABC",
                "Metadata key 'server.archiveonly' value 'ABC' for dataset (3)|drb must be a boolean",
            ),
            (
                "Truth",
                "Metadata key 'server.archiveonly' value 'Truth' for dataset (3)|drb must be a boolean",
            ),
            (
                [],
                "Metadata key 'server.archiveonly' value [] for dataset (3)|drb must be a boolean",
            ),
            (
                1.00,
                "Metadata key 'server.archiveonly' value 1.0 for dataset (3)|drb must be a boolean",
            ),
        ],
    )
    def test_mutable_archiveonly_bad(
        self, server_config, attach_dataset, value, message
    ):
        """
        Try out some invalid deletion time values.

        The value must be a valid date/time string, and it must be within the
        server's maximum retention threshold from the dataset's upload time.
        """
        ds = Dataset.query(name="drb")
        with pytest.raises(MetadataBadValue) as exc:
            Metadata.setvalue(ds, "server.archiveonly", value)
        assert str(exc.value) == message
        assert Metadata.getvalue(ds, "server.archiveonly") is None
