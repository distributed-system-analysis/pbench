import pytest

from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    OperationName,
    OperationState,
)
from pbench.server.sync import Sync, SyncSqlError


class TestSync:
    @pytest.fixture
    def fake_raise_session(self, monkeypatch, attach_dataset):
        class FakeSession:
            def query(self, **kwargs):
                raise Exception("nothing happened")

        monkeypatch.setattr("pbench.server.sync.Database.maker.begin", FakeSession())

    def test_construct(self, make_logger):
        """A few simple checks on the sync constructor, including the
        string conversion.
        """
        sync = Sync(make_logger, OperationName.UPLOAD)
        assert sync.logger is make_logger
        assert sync.component == OperationName.UPLOAD
        assert str(sync) == "<Synchronizer for component 'UPLOAD'>"

    def test_error(self, make_logger, more_datasets):
        """Test that the sync error operation writes the expected data when the
        named operation exists."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.UPLOAD)
        sync.update(drb, enabled=[OperationName.UPLOAD])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "READY", "message": None}
        }
        sync.error(drb, "this is an error")
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "FAILED", "message": "this is an error"}
        }

    def test_error_new(self, make_logger, more_datasets):
        """Test that the sync error operation creates an operation row if one
        didn't already exist."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.UPLOAD)
        assert Metadata.getvalue(drb, "dataset.operations") == {}
        sync.error(drb, "this is an error")
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "FAILED", "message": "this is an error"}
        }

    def test_error_long(self, make_logger, more_datasets):
        """Test handling of long error messages"""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.UPLOAD)
        sync.update(drb, enabled=[OperationName.UPLOAD])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "READY", "message": None}
        }
        sync.error(drb, "tenletters" * 26)
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "FAILED", "message": "tenletters" * 26}
        }

    def test_update_state(self, make_logger, more_datasets):
        """Test that the sync update operation sets the component state as
        specified.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.UPLOAD)
        sync.update(drb, None, [OperationName.DELETE, OperationName.INDEX])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "DELETE": {"state": "READY", "message": None},
            "INDEX": {"state": "READY", "message": None},
        }
        sync1 = Sync(make_logger, OperationName.INDEX)
        sync1.update(drb, OperationState.OK)
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "DELETE": {"state": "READY", "message": None},
            "INDEX": {"state": "OK", "message": "OK"},
        }
        sync2 = Sync(make_logger, OperationName.DELETE)
        sync2.update(drb, OperationState.FAILED, message="oops")
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "DELETE": {"state": "FAILED", "message": "oops"},
            "INDEX": {"state": "OK", "message": "OK"},
        }

    def test_update_state_new(self, make_logger, more_datasets):
        """Test that the sync update operation updates component state when the
        specified component wasn't present.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.INDEX)
        sync.update(drb, None, [OperationName.UPLOAD, OperationName.DELETE])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "READY", "message": None},
            "DELETE": {"state": "READY", "message": None},
        }
        sync.update(drb, state=OperationState.OK)
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "INDEX": {"state": "OK", "message": None},
            "UPLOAD": {"state": "READY", "message": None},
            "DELETE": {"state": "READY", "message": None},
        }

    def test_update_state_update(self, make_logger, more_datasets):
        """Test that sync update records operation state."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.INDEX)
        sync.update(drb, None, [OperationName.DELETE, OperationName.INDEX])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "DELETE": {"state": "READY", "message": None},
            "INDEX": {"state": "READY", "message": None},
        }
        sync.update(drb, state=OperationState.FAILED, message="failed")
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "DELETE": {"state": "READY", "message": None},
            "INDEX": {"state": "FAILED", "message": "failed"},
        }

    def test_update_state_update_long(self, make_logger, more_datasets):
        """Test that sync update allows messages over 255 characters."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.INDEX)
        sync.update(drb, None, [OperationName.DELETE, OperationName.INDEX])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "DELETE": {"state": "READY", "message": None},
            "INDEX": {"state": "READY", "message": None},
        }
        sync.update(drb, state=OperationState.FAILED, message="tenletters" * 26)
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "DELETE": {"state": "READY", "message": None},
            "INDEX": {"state": "FAILED", "message": "tenletters" * 26},
        }

    def test_update_enable(self, make_logger, more_datasets):
        """Test that sync update correctly enables specified operations."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.INDEX)
        sync.update(drb, enabled=[OperationName.REINDEX])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "REINDEX": {"state": "READY", "message": None}
        }
        sync.update(drb, enabled=[OperationName.DELETE, OperationName.INDEX])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "DELETE": {"state": "READY", "message": None},
            "INDEX": {"state": "READY", "message": None},
            "REINDEX": {"state": "READY", "message": None},
        }

    def test_update_enable_message(self, make_logger, more_datasets):
        """Test that sync update can enable new operations and set a message."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.DELETE)
        sync.update(drb, enabled=[OperationName.INDEX])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "INDEX": {"state": "READY", "message": None}
        }
        sync.update(
            drb, enabled=[OperationName.UPLOAD, OperationName.INDEX], message="bad"
        )
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "READY", "message": None},
            "INDEX": {"state": "READY", "message": None},
            "DELETE": {"state": "FAILED", "message": "bad"},
        }

    def test_update_state_enable(self, make_logger, more_datasets):
        """Verify sync update behavior with both completed and enabled
        operations
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.INDEX)
        sync.update(drb, state=OperationState.WORKING)
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "INDEX": {"state": "WORKING", "message": None}
        }
        sync.update(
            drb,
            state=OperationState.OK,
            enabled=[OperationName.UPLOAD, OperationName.TOOLINDEX],
        )
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "INDEX": {"state": "OK", "message": "OK"},
            "UPLOAD": {"state": "READY", "message": None},
            "TOOLINDEX": {"state": "READY", "message": None},
        }

    def test_update_state_enable_status(self, make_logger, more_datasets):
        """Test sync update with all three options, to mark a completed
        operation, enable a new operation, and set a message.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.UPLOAD)
        sync.update(drb, state=OperationState.WORKING)
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "WORKING", "message": None}
        }
        sync.update(
            drb, state=OperationState.OK, enabled=[OperationName.INDEX], message="plugh"
        )
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "UPLOAD": {"state": "OK", "message": "plugh"},
            "INDEX": {"state": "READY", "message": None},
        }

    def test_tool_sequence(self, make_logger, more_datasets):
        """Test sync update with INDEX and INDEX_TOOL does not find the data
        again.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.INDEX)
        sync.update(drb, state=OperationState.OK, enabled=[OperationName.TOOLINDEX])
        assert Metadata.getvalue(drb, "dataset.operations") == {
            "INDEX": {"state": "OK", "message": None},
            "TOOLINDEX": {"state": "READY", "message": None},
        }
        dataset_l = sync.next()
        assert len(dataset_l) == 0, f"{dataset_l!r}"

    def test_next(self, make_logger, more_datasets):
        """Test that the sync next operation returns the datasets enabled for
        the requested operation
        """
        drb = Dataset.query(name="drb")
        fio_1 = Dataset.query(name="fio_1")
        fio_2 = Dataset.query(name="fio_2")
        sync = Sync(make_logger, OperationName.INDEX)
        sync.update(drb, None, [OperationName.INDEX])
        sync.update(fio_1, None, [OperationName.INDEX])
        sync.update(fio_2, None, [OperationName.TOOLINDEX])
        list = sync.next()
        assert ["drb", "fio_1"] == sorted(d.name for d in list)

    def test_next_failure(self, fake_raise_session, make_logger):
        """Test the behavior of the sync next behavior when a DB failure
        occurs.
        """

        sync = Sync(make_logger, OperationName.INDEX)
        with pytest.raises(SyncSqlError):
            sync.next()

    def test_update_failure(self, fake_raise_session, make_logger):
        """Test the behavior of the sync update behavior when a DB failure
        occurs.
        """

        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.INDEX)
        with pytest.raises(SyncSqlError):
            sync.update(drb, OperationState.OK)

    def test_error_failure(self, fake_raise_session, make_logger):
        """Test the behavior of the sync error behavior when a DB failure
        occurs.
        """

        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, OperationName.INDEX)
        with pytest.raises(SyncSqlError):
            sync.error(drb, "this won't work")
