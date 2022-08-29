from argparse import Namespace
from logging import Logger
from os import stat_result
from typing import Dict, List, Optional

from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.indexing_tarballs import Index, TarballData
from pbench.server.sync import Operation, Sync


class FakeIdxContext:
    def __init__(self, config: PbenchServerConfig, logger: Logger):
        self.config = config
        self.logger = logger


class FakeSync(Sync):
    tarballs: Dict[Operation, List[Dataset]] = {}
    called: List[str] = []

    @classmethod
    def reset(cls):
        cls.tarballs = {}
        cls.called = []

    def __init__(self, logger: Logger, component: str):
        self.logger = logger
        self.component = component

    def next(self, operation: Operation) -> List[Dataset]:
        __class__.called.append(f"next-{operation.name}")
        assert operation in __class__.tarballs
        return __class__.tarballs[operation]

    def update(
        self,
        dataset: Dataset,
        did: Optional[Operation],
        enabled: Optional[List[Operation]],
    ):
        pass

    def error(self, dataset: Dataset, message: str):
        pass


class TestIndexingTarballs:
    def test_construct(self, monkeypatch, server_config):
        monkeypatch.setattr(Sync, "__new__", FakeSync.__new__)
        logger = get_pbench_logger("unit_test", server_config)
        i = Index(
            "test",
            Namespace(index_tool_data=False, re_index=False),
            FakeIdxContext(server_config, logger),
        )
        assert not i.options.index_tool_data
        assert i.idxctx.config == server_config
        assert i.filetree.datasets == {}
        assert i.sync.component == "index"

    def test_collect_tb_empty(self, monkeypatch, server_config):
        FakeSync.reset()
        monkeypatch.setattr("pbench.server.indexing_tarballs.Sync", FakeSync)
        logger = get_pbench_logger("unit_test", server_config)
        index = Index(
            "test",
            Namespace(index_tool_data=False, re_index=False),
            FakeIdxContext(server_config, logger),
        )
        FakeSync.tarballs[Operation.INDEX] = []
        tb_list = index.collect_tb()
        assert FakeSync.called == ["next-INDEX"]
        assert tb_list == (0, [])

    def test_collect_tb(self, monkeypatch, server_config):
        def getvalue(dataset: Dataset, key: str) -> str:
            assert key == Metadata.TARBALL_PATH
            return f"{dataset.name}.tar.xz"

        def stat(file: str) -> stat_result:
            assert "ds1" in file or "ds2" in file
            size = 5 if "ds1" in file else 2
            return stat_result([0o777, 123, 300, 1, 100, 100, size, 0, 0, 0])

        FakeSync.reset()
        monkeypatch.setattr(Metadata, "getvalue", getvalue)
        monkeypatch.setattr("pbench.server.indexing_tarballs.Sync", FakeSync)
        monkeypatch.setattr("os.stat", stat)
        logger = get_pbench_logger("unit_test", server_config)
        index = Index(
            "test",
            Namespace(index_tool_data=False, re_index=False),
            FakeIdxContext(server_config, logger),
        )
        ds1 = Dataset(name="ds1", resource_id="ABC")
        ds2 = Dataset(name="ds2", resource_id="ACDF")
        ds_list = [ds1, ds2]
        FakeSync.tarballs[Operation.INDEX] = ds_list
        tb_list = index.collect_tb()
        assert FakeSync.called == ["next-INDEX"]
        assert tb_list == (
            0,
            [
                TarballData(dataset=ds2, size=2, tarball=f"{ds2.name}.tar.xz"),
                TarballData(dataset=ds1, size=5, tarball=f"{ds1.name}.tar.xz"),
            ],
        )
