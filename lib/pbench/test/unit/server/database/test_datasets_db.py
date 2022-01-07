import pytest
from pbench.server.database.models.datasets import (
    Dataset,
    States,
    DatasetBadParameterType,
    DatasetBadStateTransition,
    DatasetTerminalStateViolation,
    DatasetNotFound,
)
from pbench.server.database.models.users import User


class TestDatasets:
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
        assert ds.created is None
        assert ds.uploaded <= ds.transition
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
        ds1 = Dataset.query(name="fio")
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

        ds2 = Dataset.attach(name="fio", state=States.INDEXED)
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
            Dataset.attach(name="venus", state=States.UPLOADING)

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

        ds2 = Dataset.query(name="fio")
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

        ds2 = Dataset.query(name="rover")
        assert ds2.owner == ds1.owner
        assert ds2.controller == ds1.controller
        assert ds2.name == ds1.name
        assert ds2.state == States.QUARANTINED
        assert ds2.md5 is ds1.md5
        assert ds2.id is ds1.id

    def test_query_name(self, db_session, create_user):
        """ Test that we can find a dataset by name alone
        """
        ds1 = Dataset(
            owner=create_user.username,
            controller="frodo",
            name="fio",
            state=States.INDEXING,
        )
        ds1.add()

        ds2 = Dataset.query(name="fio")
        assert ds2.name == "fio"
        assert ds2.owner == ds1.owner
        assert ds2.controller == ds1.controller
        assert ds2.name == ds1.name
        assert ds2.state == ds1.state
        assert ds2.md5 == ds1.md5
        assert ds2.id == ds1.id

    def test_advanced_good(self, db_session, create_user):
        """ Test advancing the state of a dataset
        """
        ds = Dataset(owner=create_user.username, controller="frodo", name="fio")
        ds.add()
        ds.advance(States.UPLOADED)
        assert ds.state == States.UPLOADED
        assert ds.uploaded <= ds.transition

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

    def test_delete(self, db_session, create_user):
        """ Test that we can delete a dataset
        """
        ds1 = Dataset(
            owner=create_user.username,
            controller="frodo",
            name="foobar",
            state=States.INDEXING,
        )
        ds1.add()

        # we can find it
        ds2 = Dataset.attach(name="foobar", state=States.INDEXED)
        assert ds2.name == ds1.name

        ds2.delete()

        with pytest.raises(DatasetNotFound):
            Dataset.query(name="foobar")
