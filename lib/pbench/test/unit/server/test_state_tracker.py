import pytest
from pbench.server.database.models.datasets import (
    Dataset,
    States,
    Metadata,
    DatasetBadParameterType,
    DatasetBadStateTransition,
    DatasetTerminalStateViolation,
    DatasetNotFound,
    MetadataNotFound,
    MetadataBadKey,
    MetadataMissingKeyValue,
    MetadataDuplicateKey,
)
from pbench.server.database.models.users import User


class TestStateTracker:
    def test_state_enum(self):
        """ Test the States ENUM properties
        """
        assert len(States.__members__) == 9
        for n, s in States.__members__.items():
            assert str(s) == s.friendly
            assert s.mutating == (
                "ing" in s.friendly
            ), f"Enum {n} name and state don't match"

    def test_construct(self, db_session, create_user):
        """ Test dataset contructor
        """
        user = create_user
        ds = Dataset(owner=user.username, controller="frodo", name="fio")
        ds.add()
        assert ds.owner == user
        assert ds.controller == "frodo"
        assert ds.name == "fio"
        assert ds.state == States.UPLOADING
        assert ds.md5 is None
        assert ds.created <= ds.transition
        assert ds.id is not None
        assert "test(1)|frodo|fio" == str(ds)

    def test_dataset_survives_user(self, db_session, create_user):
        """The Dataset isn't automatically removed when the referenced
        user is removed.
        """
        user = create_user
        ds = Dataset(owner=user.username, controller="frodo", name="fio")
        ds.add()
        User.delete(username=user.username)
        ds1 = Dataset.attach(controller="frodo", name="fio")
        assert ds1 == ds

    def test_construct_bad_owner(self):
        """Test with a non-existent username
        """
        with pytest.raises(DatasetBadParameterType):
            Dataset(owner="notme", controller="frodo", name="fio")

    def test_construct_bad_state(self, db_session, create_user):
        """Test with a non-States state value
        """
        with pytest.raises(DatasetBadParameterType):
            Dataset(
                owner=create_user.username,
                controller="frodo",
                name="fio",
                state="notStates",
            )

    def test_attach_exists(self, db_session, create_user):
        """ Test that we can attach to a dataset
        """
        ds1 = Dataset(
            owner=create_user.username,
            controller="frodo",
            name="fio",
            state=States.INDEXING,
        )
        ds1.add()

        ds2 = Dataset.attach(controller="frodo", name="fio", state=States.INDEXED)
        assert ds2.owner == ds1.owner
        assert ds2.controller == ds1.controller
        assert ds2.name == ds1.name
        assert ds2.state == States.INDEXED
        assert ds2.md5 is ds1.md5
        assert ds2.id is ds1.id

    def test_attach_none(self, db_session):
        """ Test expected failure when we try to attach to a dataset that
        does not exist.
        """
        with pytest.raises(DatasetNotFound):
            Dataset.attach(controller="frodo", name="venus", state=States.UPLOADING)

    def test_attach_controller_path(self, db_session, create_user):
        """ Test that we can attach using controller and name to a
        dataset created by file path.
        """
        ds1 = Dataset(
            owner=create_user.username,
            path="/foo/frodo/fio.tar.xz",
            state=States.INDEXING,
        )
        ds1.add()

        ds2 = Dataset.attach(controller="frodo", name="fio")
        assert ds2.owner == ds1.owner
        assert ds2.controller == ds1.controller
        assert ds2.name == ds1.name
        assert ds2.state == States.INDEXING
        assert ds2.md5 is ds1.md5
        assert ds2.id is ds1.id

    def test_attach_filename(self, db_session, create_user):
        """ Test that we can create a dataset using the full tarball
        file path.
        """
        ds1 = Dataset(
            owner="test", path="/foo/bilbo/rover.tar.xz", state=States.QUARANTINED
        )
        ds1.add()

        ds2 = Dataset.attach(controller="bilbo", name="rover")
        assert ds2.owner == ds1.owner
        assert ds2.controller == ds1.controller
        assert ds2.name == ds1.name
        assert ds2.state == States.QUARANTINED
        assert ds2.md5 is ds1.md5
        assert ds2.id is ds1.id

    def test_advanced_good(self, db_session, create_user):
        """ Test advancing the state of a dataset
        """
        ds = Dataset(owner=create_user.username, controller="frodo", name="fio")
        ds.add()
        ds.advance(States.UPLOADED)
        assert ds.state == States.UPLOADED
        assert ds.created <= ds.transition

    def test_advanced_bad_state(self, db_session, create_user):
        """Test with a non-States state value
        """
        ds = Dataset(owner=create_user.username, controller="frodo", name="fio")
        ds.add()
        with pytest.raises(DatasetBadParameterType):
            ds.advance("notStates")

    def test_advanced_illegal(self, db_session, create_user):
        """ Test that we can't advance to a state that's not a
        successor to the initial state.
        """
        ds = Dataset(owner=create_user.username, controller="frodo", name="fio")
        ds.add()
        with pytest.raises(DatasetBadStateTransition):
            ds.advance(States.EXPIRED)

    def test_advanced_terminal(self, db_session, create_user):
        """ Test that we can't advance from a terminal state
        """
        ds = Dataset(
            owner=create_user.username,
            controller="frodo",
            name="fio",
            state=States.EXPIRED,
        )
        ds.add()
        with pytest.raises(DatasetTerminalStateViolation):
            ds.advance(States.UPLOADING)

    def test_lifecycle(self, db_session, create_user):
        """ Advance a dataset through the entire lifecycle using the state
        transition dict.
        """
        ds = Dataset(owner=create_user.username, controller="frodo", name="fio")
        ds.add()
        assert ds.state == States.UPLOADING
        beenthere = [ds.state]
        while ds.state in Dataset.transitions:
            advances = Dataset.transitions[ds.state]
            for n in advances:
                if n not in beenthere:
                    next = n
                    break
            else:
                break  # avoid infinite reindex loop!
            beenthere.append(next)
            ds.advance(next)
            assert ds.state == next
        lifecycle = ",".join([s.name for s in beenthere])
        assert (
            lifecycle
            == "UPLOADING,UPLOADED,UNPACKING,UNPACKED,INDEXING,INDEXED,EXPIRING,EXPIRED"
        )

    def test_metadata(self, db_session, create_user):
        """ Various tests on Metadata keys
        """
        # See if we can create a metadata row
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        assert ds.metadatas == []
        m = Metadata.create(key=Metadata.REINDEX, value="TRUE", dataset=ds)
        assert m is not None
        assert ds.metadatas == [m]

        # Try to get it back
        m1 = Metadata.get(ds, Metadata.REINDEX)
        assert m1.key == m.key
        assert m1.value == m.value
        assert m.id == m1.id
        assert m.dataset_ref == m1.dataset_ref

        # Check the str()
        assert "test(1)|frodo|fio>>REINDEX" == str(m)

        # Try to get a metadata key that doesn't exist
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, Metadata.TARBALL_PATH)
        assert exc.value.dataset == ds
        assert exc.value.key == Metadata.TARBALL_PATH

        # Try to remove a metadata key that doesn't exist (No-op)
        Metadata.remove(ds, Metadata.TARBALL_PATH)

        # Try to create a metadata with a bad key
        badkey = "THISISNOTTHEKEYYOURELOOKINGFOR"
        with pytest.raises(MetadataBadKey) as exc:
            Metadata(key=badkey, value=None)
        assert exc.value.key == badkey

        # Try to create a key without a value
        with pytest.raises(MetadataMissingKeyValue):
            Metadata(key=Metadata.REINDEX)

        # Try to add a duplicate metadata key
        with pytest.raises(MetadataDuplicateKey) as exc:
            m1 = Metadata(key=Metadata.REINDEX, value="IRRELEVANT")
            m1.add(ds)
        assert exc.value.key == Metadata.REINDEX
        assert exc.value.dataset == ds
        assert ds.metadatas == [m]

        # Try to add a Metadata key to something that's not a dataset
        with pytest.raises(DatasetBadParameterType) as exc:
            m1 = Metadata(key=Metadata.TARBALL_PATH, value="DONTCARE")
            m1.add("foobar")
        assert exc.value.bad_value == "foobar"
        assert exc.value.expected_type == Dataset.__name__

        # Try to create a Metadata with a bad value for the dataset
        with pytest.raises(DatasetBadParameterType) as exc:
            m1 = Metadata.create(key=Metadata.REINDEX, value="TRUE", dataset=[ds])
        assert exc.value.bad_value == [ds]
        assert exc.value.expected_type == Dataset.__name__

        # Try to update the metadata key
        m.value = "False"
        m.update()
        m1 = Metadata.get(ds, Metadata.REINDEX)
        assert m.id == m1.id
        assert m.dataset_ref == m1.dataset_ref
        assert m.key == m1.key
        assert m.value == "False"

        # Delete the key and make sure its gone
        m.delete()
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, Metadata.REINDEX)
        assert exc.value.dataset == ds
        assert exc.value.key == Metadata.REINDEX
        assert ds.metadatas == []

    def test_metadata_remove(self, db_session, create_user):
        """ Test that we can remove a Metadata key
        """
        ds = Dataset.create(owner=create_user.username, controller="frodo", name="fio")
        assert ds.metadatas == []
        m = Metadata(key=Metadata.ARCHIVED, value="TRUE")
        m.add(ds)
        assert ds.metadatas == [m]

        Metadata.remove(ds, Metadata.ARCHIVED)
        assert ds.metadatas == []
        with pytest.raises(MetadataNotFound) as exc:
            Metadata.get(ds, Metadata.ARCHIVED)
        assert exc.value.dataset == ds
        assert exc.value.key == Metadata.ARCHIVED

        Metadata.remove(ds, Metadata.REINDEX)
        assert ds.metadatas == []