import pytest

from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.sync import Operation, Sync, SyncSqlError


class TestSync:
    def test_construct(self, make_logger):
        """A few simple checks on the sync constructor, including the
        string conversion.
        """
        sync = Sync(make_logger, "test")
        assert sync.logger is make_logger
        assert sync.component == "test"
        assert str(sync) == "<Synchronizer for component 'test'>"

    def test_next(self, make_logger, more_datasets):
        """Test that the sync next operation returns the datasets enabled for
        the requested operation
        """
        drb = Dataset.query(name="drb")
        fio_1 = Dataset.query(name="fio_1")
        fio_2 = Dataset.query(name="fio_2")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK"])
        Metadata.setvalue(fio_1, Metadata.OPERATION, ["UNPACK"])
        Metadata.setvalue(fio_2, Metadata.OPERATION, ["BACKUP"])
        list = sync.next(Operation.UNPACK)
        assert ["drb", "fio_1"] == sorted(d.name for d in list)

    def test_next_failure(self, monkeypatch, make_logger):
        """Test the behavior of the sync next behavior when a DB failure
        occurs.
        """

        def fake_query(self, *entities, **kwargs):
            raise Exception("nothing happened")

        sync = Sync(make_logger, "test")
        monkeypatch.setattr("pbench.server.sync.Database.db_session.query", fake_query)
        with pytest.raises(SyncSqlError):
            sync.next(Operation.UNPACK)

    def test_error(self, make_logger, more_datasets):
        """Test that the sync error operation writes the expected metadata."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        sync.error(drb, "this is an error")
        assert Metadata.getvalue(drb, "server.status.test") == "this is an error"

    def test_update_did(self, make_logger, more_datasets):
        """Test that the sync update operation removes the specified "did"
        operation from the pending operation set.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK", "BACKUP"])
        sync.update(drb, did=Operation.BACKUP)
        assert Metadata.getvalue(drb, "server.status.test") == "ok"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == ["UNPACK"]

    def test_update_did_not_enabled(self, make_logger, more_datasets):
        """Test that the sync update operation behaves correctly when the
        specified "did" operation is not in the enabled operation set.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK", "BACKUP"])
        sync.update(drb, did=Operation.INDEX)
        assert Metadata.getvalue(drb, "server.status.test") == "ok"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == ["BACKUP", "UNPACK"]

    def test_update_did_status(self, make_logger, more_datasets):
        """Test that sync update records operation status."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK", "BACKUP"])
        sync.update(drb, did=Operation.BACKUP, status="failed")
        assert Metadata.getvalue(drb, "server.status.test") == "failed"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == ["UNPACK"]

    def test_update_enable(self, make_logger, more_datasets):
        """Test that sync update correctly enables specified operations."""
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK"])
        sync.update(drb, enabled=[Operation.BACKUP, Operation.INDEX])
        assert Metadata.getvalue(drb, "server.status.test") is None
        assert Metadata.getvalue(drb, Metadata.OPERATION) == [
            "BACKUP",
            "INDEX",
            "UNPACK",
        ]

    def test_update_enable_status(self, make_logger, more_datasets):
        """Test that sync update can enable new operations and set a status
        message.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK"])
        sync.update(drb, enabled=[Operation.BACKUP, Operation.INDEX], status="bad")
        assert Metadata.getvalue(drb, "server.status.test") == "bad"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == [
            "BACKUP",
            "INDEX",
            "UNPACK",
        ]

    def test_update_did_enable(self, make_logger, more_datasets):
        """Verify sync update behavior with "did", "enabled" operation set,
        with the default success message.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["INDEX", "UNPACK"])
        sync.update(
            drb, did=Operation.UNPACK, enabled=[Operation.BACKUP, Operation.INDEX_TOOL]
        )
        assert Metadata.getvalue(drb, "server.status.test") == "ok"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == [
            "BACKUP",
            "INDEX",
            "INDEX_TOOL",
        ]

    def test_update_did_enable_status(self, make_logger, more_datasets):
        """Test sync update with all three options, to remove a completed
        operation, enable a new operation, and set a message.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK"])
        sync.update(
            drb, did=Operation.UNPACK, enabled=[Operation.INDEX], status="plugh"
        )
        assert Metadata.getvalue(drb, "server.status.test") == "plugh"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == ["INDEX"]

    def test_tool_sequence(self, make_logger, more_datasets):
        """Test sync update with INDEX and INDEX_TOOL does not find the data
        again.
        """
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["INDEX"])
        sync.update(drb, did=Operation.INDEX, enabled=[Operation.INDEX_TOOL])
        assert Metadata.getvalue(drb, Metadata.OPERATION) == ["INDEX_TOOL"]
        dataset_l = sync.next(Operation.INDEX)
        assert len(dataset_l) == 0, f"{dataset_l!r}"
