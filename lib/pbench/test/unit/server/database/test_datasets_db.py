from datetime import datetime
from freezegun.api import freeze_time
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
        """Test the States ENUM properties"""
        assert len(States.__members__) == 7
        for n, s in States.__members__.items():
            assert str(s) == s.friendly
            assert s.mutating == (
                "ing" in s.friendly
            ), f"Enum {n} name and state don't match"

    def test_construct(self, db_session, create_user):
        """Test dataset contructor"""
        user = create_user
        with freeze_time("1970-01-01"):
            ds = Dataset(owner=user.username, name="fio", resource_id="f00b0ad")
            ds.add()
        assert ds.owner == user
        assert ds.name == "fio"
        assert ds.state == States.UPLOADING
        assert ds.resource_id == "f00b0ad"

        # The "uploaded" and "transition" timestamps will be set automatically
        # to the current time, and should initially be identical. The
        # "created" timestamp cannot be set until a tarball has been fully
        # uploaded and we unpack and process the metadata.log file; the
        # constructor leaves this empty to avoid confusion.
        assert ds.created is None
        assert ds.uploaded <= ds.transition
        assert ds.id is not None
        assert "test(1)|fio" == str(ds)
        assert ds.as_dict() == {
            "access": "private",
            "created": None,
            "name": "fio",
            "owner": "test",
            "state": "Uploading",
            "transition": "1970-01-01T00:00:00+00:00",
            "uploaded": "1970-01-01T00:00:00+00:00",
            "metalog": None,
        }

    def test_dataset_survives_user(self, db_session, create_user):
        """The Dataset isn't automatically removed when the referenced
        user is removed.
        """
        user = create_user
        ds = Dataset(owner=user.username, name="fio", resource_id="deadbeef")
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
            "created": "2020-02-15T00:00:00+00:00",
            "name": "drb",
            "owner": "drb",
            "state": "Indexed",
            "transition": "1970-01-01T00:42:00+00:00",
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
        }

    def test_construct_bad_owner(self, db_session):
        """Test with a non-existent username"""
        with pytest.raises(DatasetBadParameterType):
            Dataset(owner="notme", name="fio")

    def test_construct_bad_state(self, db_session, create_user):
        """Test with a non-States state value"""
        with pytest.raises(DatasetBadParameterType):
            Dataset(
                owner=create_user.username,
                name="fio",
                resource_id="d00d",
                state="notStates",
            )

    def test_attach_exists(self, db_session, create_user):
        """Test that we can attach to a dataset"""
        ds1 = Dataset(
            owner=create_user.username,
            name="fio",
            resource_id="bib",
            state=States.INDEXING,
        )
        ds1.add()

        ds2 = Dataset.attach(resource_id=ds1.resource_id, state=States.INDEXED)
        assert ds2.owner == ds1.owner
        assert ds2.name == ds1.name
        assert ds2.state == States.INDEXED
        assert ds2.resource_id is ds1.resource_id
        assert ds2.id is ds1.id

    def test_attach_none(self, db_session):
        """Test expected failure when we try to attach to a dataset that
        does not exist.
        """
        with pytest.raises(DatasetNotFound):
            Dataset.attach(resource_id="xyzzy", state=States.UPLOADING)

    def test_query_name(self, db_session, create_user):
        """Test that we can find a dataset by name alone"""
        ds1 = Dataset(
            owner=create_user.username,
            resource_id="deed1e",
            name="fio",
            state=States.INDEXING,
        )
        ds1.add()

        ds2 = Dataset.query(name="fio")
        assert ds2.name == "fio"
        assert ds2.owner == ds1.owner
        assert ds2.name == ds1.name
        assert ds2.state == ds1.state
        assert ds2.resource_id == ds1.resource_id
        assert ds2.id == ds1.id

    def test_advanced_good(self, db_session, create_user):
        """Test advancing the state of a dataset"""
        with freeze_time("2525-05-25T15:15"):
            ds = Dataset(owner=create_user.username, name="fio", resource_id="beefeed")
            ds.created = datetime(2020, 1, 25, 23, 14)
            ds.add()
        with freeze_time("2525-08-25T15:25"):
            ds.advance(States.UPLOADED)
        assert ds.state == States.UPLOADED
        assert ds.uploaded <= ds.transition
        assert ds.as_dict() == {
            "access": "private",
            "created": "2020-01-25T23:14:00+00:00",
            "name": "fio",
            "owner": "test",
            "state": "Uploaded",
            "transition": "2525-08-25T15:25:00+00:00",
            "uploaded": "2525-05-25T15:15:00+00:00",
            "metalog": None,
        }

    def test_advanced_bad_state(self, db_session, create_user):
        """Test with a non-States state value"""
        ds = Dataset(owner=create_user.username, name="fio", resource_id="feebeed")
        ds.add()
        with pytest.raises(DatasetBadParameterType):
            ds.advance("notStates")

    def test_advanced_illegal(self, db_session, create_user):
        """Test that we can't advance to a state that's not a
        successor to the initial state.
        """
        ds = Dataset(owner=create_user.username, name="fio", resource_id="debead")
        ds.add()
        with pytest.raises(DatasetBadStateTransition):
            ds.advance(States.DELETED)

    def test_advanced_terminal(self, db_session, create_user):
        """Test that we can't advance from a terminal state"""
        ds = Dataset(
            owner=create_user.username,
            name="fio",
            resource_id="beadde",
            state=States.DELETED,
        )
        ds.add()
        with pytest.raises(DatasetTerminalStateViolation):
            ds.advance(States.UPLOADING)

    def test_lifecycle(self, db_session, create_user):
        """Advance a dataset through the entire lifecycle using the state
        transition dict.
        """
        ds = Dataset(owner=create_user.username, name="fio", resource_id="beaddee")
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
        assert lifecycle == "UPLOADING,UPLOADED,INDEXING,INDEXED,DELETING,DELETED"

    def test_delete(self, db_session, create_user):
        """Test that we can delete a dataset"""
        ds1 = Dataset(
            owner=create_user.username,
            name="foobar",
            resource_id="f00dea7",
            state=States.INDEXING,
        )
        ds1.add()

        # we can find it
        ds2 = Dataset.query(resource_id=ds1.resource_id)
        assert ds2.name == ds1.name

        ds2.delete()

        with pytest.raises(DatasetNotFound):
            Dataset.query(resource_id=ds1.resource_id)
