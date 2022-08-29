from pbench.common.logger import get_pbench_logger
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.sync import Operation, Sync


class TestSync:
    def test_construct(self, server_config):
        logger = get_pbench_logger(__name__, server_config)
        sync = Sync(logger, "test")
        assert sync.logger is logger
        assert sync.component == "test"

    def test_next(self, server_config, more_datasets):
        drb = Dataset.query(name="drb")
        fio_1 = Dataset.query(name="fio_1")
        fio_2 = Dataset.query(name="fio_2")
        sync = Sync(get_pbench_logger(__name__, server_config), "test")
        Metadata.setvalue(drb, Metadata.OPERATION, "UNPACK")
        Metadata.setvalue(fio_1, Metadata.OPERATION, "UNPACK")
        Metadata.setvalue(fio_2, Metadata.OPERATION, "BACKUP")
        list = sync.next(Operation.UNPACK)
        assert ["drb", "fio_1"] == sorted([d.name for d in list])
