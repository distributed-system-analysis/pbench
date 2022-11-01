from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.sync import Operation, Sync


class TestSync:
    def test_construct(self, make_logger):
        sync = Sync(make_logger, "test")
        assert sync.logger is make_logger
        assert sync.component == "test"
        assert str(sync) == "<Synchronizer for component 'test'>"

    def test_next(self, make_logger, more_datasets):
        drb = Dataset.query(name="drb")
        fio_1 = Dataset.query(name="fio_1")
        fio_2 = Dataset.query(name="fio_2")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK"])
        Metadata.setvalue(fio_1, Metadata.OPERATION, ["UNPACK"])
        Metadata.setvalue(fio_2, Metadata.OPERATION, ["BACKUP"])
        list = sync.next(Operation.UNPACK)
        assert ["drb", "fio_1"] == sorted([d.name for d in list])

    def test_error(self, make_logger, more_datasets):
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        sync.error(drb, "this is an error")
        assert Metadata.getvalue(drb, "server.status.test") == "this is an error"

    def test_update_did(self, make_logger, more_datasets):
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK", "BACKUP"])
        sync.update(drb, did=Operation.BACKUP)
        assert Metadata.getvalue(drb, "server.status.test") is None
        assert Metadata.getvalue(drb, Metadata.OPERATION) == ["UNPACK"]

    def test_update_did_status(self, make_logger, more_datasets):
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK", "BACKUP"])
        sync.update(drb, did=Operation.BACKUP, status="failed")
        assert Metadata.getvalue(drb, "server.status.test") == "failed"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == ["UNPACK"]

    def test_update_enable(self, make_logger, more_datasets):
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK"])
        sync.update(drb, enabled=[Operation.BACKUP, Operation.COPY_SOS])
        assert Metadata.getvalue(drb, "server.status.test") == "ok"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == [
            "BACKUP",
            "COPY_SOS",
            "UNPACK",
        ]

    def test_update_enable_status(self, make_logger, more_datasets):
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK"])
        sync.update(drb, enabled=[Operation.BACKUP, Operation.COPY_SOS], status="bad")
        assert Metadata.getvalue(drb, "server.status.test") == "bad"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == [
            "BACKUP",
            "COPY_SOS",
            "UNPACK",
        ]

    def test_update_did_enable(self, make_logger, more_datasets):
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["INDEX", "UNPACK"])
        sync.update(
            drb, did=Operation.UNPACK, enabled=[Operation.BACKUP, Operation.COPY_SOS]
        )
        assert Metadata.getvalue(drb, "server.status.test") == "ok"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == [
            "BACKUP",
            "COPY_SOS",
            "INDEX",
        ]

    def test_update_did_enable_status(self, make_logger, more_datasets):
        drb = Dataset.query(name="drb")
        sync = Sync(make_logger, "test")
        Metadata.setvalue(drb, Metadata.OPERATION, ["UNPACK"])
        sync.update(
            drb, did=Operation.UNPACK, enabled=[Operation.COPY_SOS], status="plugh"
        )
        assert Metadata.getvalue(drb, "server.status.test") == "plugh"
        assert Metadata.getvalue(drb, Metadata.OPERATION) == ["COPY_SOS"]
