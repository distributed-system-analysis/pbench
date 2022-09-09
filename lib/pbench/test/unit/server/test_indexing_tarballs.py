from argparse import Namespace
from logging import Logger
from os import stat_result
from pathlib import Path
import time
from typing import Dict, List, Optional

import pytest

from pbench.client import JSONARRAY, JSONVALUE
from pbench.server import PbenchServerConfig
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    MetadataBadKey,
    States,
)
from pbench.server.indexing_tarballs import Index, TarballData
from pbench.server.sync import Operation


class FakeDataset:
    logger: Logger
    new_state: Optional[States] = None

    def __init__(self, name: str, resource_id: str):
        self.name = name
        self.resource_id = resource_id
        self.owner_id = 1

    def advance(self, state: States):
        __class__.new_state = state

    @classmethod
    def reset(cls):
        cls.new_state = None


class FakeMetadata:
    INDEX_MAP = Metadata.INDEX_MAP
    REINDEX = Metadata.REINDEX
    TARBALL_PATH = Metadata.TARBALL_PATH
    INDEX_MAP = Metadata.INDEX_MAP

    @staticmethod
    def getvalue(dataset: FakeDataset, key: str) -> Optional[str]:
        if key == Metadata.TARBALL_PATH:
            return f"{dataset.name}.tar.xz"
        elif key == Metadata.INDEX_MAP:
            return None
        else:
            raise MetadataBadKey(key)

    @staticmethod
    def setvalue(dataset: FakeDataset, key: str, value: JSONVALUE) -> JSONVALUE:
        return value


class FakePbenchTemplates:
    templates_updated = False

    def __init__(self, basepath, idx_prefix, logger, known_tool_handlers=None, _dbg=0):
        pass

    def update_templates(self, es_instance):
        self.templates_updated = True

    @classmethod
    def reset(cls):
        cls.templates_updated = False


class FakeReport:
    def __init__(
        self,
        config,
        name,
        es=None,
        pid=None,
        group_id=None,
        user_id=None,
        hostname=None,
        version=None,
        templates=None,
    ):
        self.config = config
        self.name = name

    def post_status(
        self, timestamp: str, doctype: str, file_to_index: Optional[Path] = None
    ) -> str:
        return "tracking_id"


class FakeIdxContext:
    def __init__(self, config: PbenchServerConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.tracking_id = None
        self.es = None
        self.TS = "FAKE_TS"
        self.templates = FakePbenchTemplates("path", "test", logger)
        self._dbg = False

    def getpid(self) -> int:
        return 1

    def getgid(self) -> int:
        return 1

    def getuid(self) -> int:
        return 1

    def gethostname(self) -> str:
        return "localhost"

    def dump_opctx(self):
        pass

    def set_tracking_id(self, id: str):
        self.tracking_id = id

    def time(self) -> float:
        return time.time()


class FakePbenchTarBall:
    make_tool_called = 0
    make_all_called = 0

    def __init__(
        self,
        idxctx: FakeIdxContext,
        username: str,
        tbarg: str,
        tmpdir: str,
        extracted_root: str,
    ):
        self.idxctx = idxctx
        self.tbname = tbarg
        self.name = Path(tbarg).name
        self.username = username
        self.extracted_root = extracted_root
        self.index_map = {"idx1": ["id1", "id2"]}

    def mk_tool_data_actions(self) -> JSONARRAY:
        __class__.make_tool_called += 1
        return [{"action": "mk_tool_data_actions", "name": self.name}]

    def make_all_actions(self) -> JSONARRAY:
        __class__.make_all_called += 1
        return [{"action": "make_all_actions", "name": self.name}]

    @classmethod
    def reset(cls):
        cls.make_tool_called = 0
        cls.make_all_called = 0


class FakeSync:
    tarballs: Dict[Operation, List[Dataset]] = {}
    called: List[str] = []
    did: Optional[Operation] = None
    updated: Optional[List[Operation]] = None
    errors: Optional[str] = None

    @classmethod
    def reset(cls):
        cls.tarballs = {}
        cls.called = []
        cls.did = None
        cls.updated = None
        cls.errors = None

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
        __class__.did = did
        __class__.updated = enabled

    def error(self, dataset: Dataset, message: str):
        __class__.errors = message


class FakeController:
    def __init__(self, path: Path, incoming: Path, results: Path, logger: Logger):
        self.name = path.name
        self.path = path
        self.incoming = incoming / self.name
        self.results = results / self.name
        self.logger = logger


class FakeTarball:
    def __init__(self, path: Path, controller: FakeController):
        self.name = path.name
        self.tarball_path = path
        self.controller = controller
        self.unpacked = f"/incoming/{path.name}"


class FakeFileTree:
    def __init__(self, config: PbenchServerConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.datasets = {}

    def find_dataset(self, resource_id: str):
        controller = FakeController(
            Path("/archive/ctrl"), Path("/incoming"), Path("/results"), self.logger
        )
        return FakeTarball(
            Path(f"/archive/ctrl/tarball-{resource_id}.tar.xz"), controller
        )


@pytest.fixture()
def mocks(monkeypatch, make_logger):
    FakeDataset.logger = make_logger
    with monkeypatch.context() as m:
        m.setattr("pbench.server.indexing_tarballs.Sync", FakeSync)
        m.setattr("pbench.server.indexing_tarballs.PbenchTarBall", FakePbenchTarBall)
        m.setattr("pbench.server.indexing_tarballs.Report", FakeReport)
        m.setattr("pbench.server.indexing_tarballs.Dataset", FakeDataset)
        m.setattr("pbench.server.indexing_tarballs.Metadata", FakeMetadata)
        m.setattr("pbench.server.indexing_tarballs.FileTree", FakeFileTree)
        yield m
    FakeSync.reset()
    FakePbenchTarBall.reset()


@pytest.fixture()
def index(server_config, make_logger):
    return Index(
        "test",
        Namespace(index_tool_data=False, re_index=False),
        FakeIdxContext(server_config, make_logger),
    )


class TestIndexingTarballs:
    def test_construct(self, mocks, index, server_config):
        assert not index.options.index_tool_data
        assert index.sync.component == "index"

    def test_collect_tb_empty(self, mocks, index):
        FakeSync.tarballs[Operation.INDEX] = []
        tb_list = index.collect_tb()
        assert FakeSync.called == ["next-INDEX"]
        assert tb_list == (0, [])

    def test_collect_tb(self, mocks, index):
        def stat(file: str) -> stat_result:
            assert "ds1" in file or "ds2" in file
            size = 5 if "ds1" in file else 2
            return stat_result([0o777, 123, 300, 1, 100, 100, size, 0, 0, 0])

        mocks.setattr("os.stat", stat)
        ds1 = FakeDataset(name="ds1", resource_id="ABC")
        ds2 = FakeDataset(name="ds2", resource_id="ACDF")
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

    def test_process_tb_none(self, mocks, index):
        stat = index.process_tb(tarballs=[])
        assert (
            stat == 0
            and not FakePbenchTarBall.make_all_called
            and not FakePbenchTarBall.make_tool_called
        )

    def test_process_tb(self, mocks, index):
        index_actions = []

        def fake_es_index(es, actions, errorsfp, logger, _dbg=0):
            index_actions.append(actions)
            return (1000, 2000, 1, 0, 0, 0)

        mocks.setattr("pbench.server.indexing_tarballs.es_index", fake_es_index)
        ds1 = FakeDataset(name="ds1", resource_id="ABC")
        ds2 = FakeDataset(name="ds2", resource_id="ACDF")
        stat = index.process_tb(
            tarballs=[
                TarballData(dataset=ds2, size=2, tarball=f"{ds2.name}.tar.xz"),
                TarballData(dataset=ds1, size=5, tarball=f"{ds1.name}.tar.xz"),
            ]
        )
        assert (
            stat == 0
            and FakePbenchTarBall.make_all_called == 2
            and not FakePbenchTarBall.make_tool_called
        )
        assert index_actions == [
            [{"action": "make_all_actions", "name": f"{ds2.name}.tar.xz"}],
            [{"action": "make_all_actions", "name": f"{ds1.name}.tar.xz"}],
        ]
