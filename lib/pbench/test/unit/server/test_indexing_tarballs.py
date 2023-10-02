from argparse import Namespace
from logging import Logger
import os
from os import stat_result
from pathlib import Path
from signal import SIGHUP
import time
from typing import Any, Dict, List, Optional, Union

import pytest

from pbench.server import (
    JSONARRAY,
    JSONOBJECT,
    JSONVALUE,
    OperationCode,
    PbenchServerConfig,
)
from pbench.server.cache_manager import LockManager, LockRef
from pbench.server.database.models.audit import AuditStatus
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    MetadataBadKey,
    OperationName,
    OperationState,
)
from pbench.server.database.models.index_map import IndexMapType
from pbench.server.indexing_tarballs import (
    Index,
    SigIntException,
    SigTermException,
    TarballData,
)
from pbench.server.templates import TemplateError


class FakeDataset:
    def __init__(self, name: str, resource_id: str):
        self.name = name
        self.resource_id = resource_id
        self.owner_id = 1

    def __repr__(self) -> str:
        return self.name

    @classmethod
    def reset(cls):
        cls.new_state = None


class FakeMetadata:
    TARBALL_PATH = Metadata.TARBALL_PATH

    no_tarball: list[str] = []
    set_values: dict[str, dict[str, Any]] = {}

    @staticmethod
    def getvalue(dataset: FakeDataset, key: str) -> Optional[JSONVALUE]:
        if key == Metadata.TARBALL_PATH:
            if dataset.name in __class__.no_tarball:
                return None
            else:
                return f"{dataset.name}.tar.xz"
        else:
            raise MetadataBadKey(key)

    @staticmethod
    def setvalue(dataset: FakeDataset, key: str, value: JSONVALUE) -> JSONVALUE:
        ds_cur = __class__.set_values.get(dataset.name, {})
        ds_cur[key] = value
        __class__.set_values[dataset.name] = ds_cur
        return value

    @classmethod
    def reset(cls):
        cls.no_tarball = []
        cls.index_map = {}
        cls.set_values = {}


class FakeIndexMap:
    index_map: dict[str, IndexMapType] = {}

    @staticmethod
    def exists(dataset: FakeDataset) -> bool:
        return bool(__class__.index_map)

    @classmethod
    def create(cls, dataset: FakeDataset, map: IndexMapType):
        cls.index_map[dataset.name] = map

    @classmethod
    def merge(cls, dataset: Dataset, new_map: IndexMapType):
        if dataset.name not in cls.index_map:
            cls.index_map[dataset.name] = new_map
        else:
            map = cls.index_map[dataset.name]
            for r, i in new_map.items():
                if r not in map:
                    map[r] = i
                else:
                    for i, d in new_map[r].items():
                        if i not in map[r]:
                            map[r][i] = d
                        else:
                            map[r][i].extend(new_map[r][i])


class FakePbenchTemplates:
    templates_updated = False
    failure: Optional[Exception] = None

    def __init__(
        self,
        lib_dir: Path,
        idx_prefix: str,
        logger: Logger,
        known_tool_handlers: JSONOBJECT = None,
        _dbg: int = 0,
    ):
        pass

    def update_templates(self, es_instance):
        __class__.templates_updated = True
        if self.failure:
            raise self.failure

    @classmethod
    def reset(cls):
        cls.templates_updated = False
        cls.failure = None


class FakeReport:
    reported = False
    failure: Optional[Exception] = None

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
        __class__.reported = True
        if self.failure:
            raise self.failure
        return "tracking_id"

    @classmethod
    def reset(cls):
        cls.reported = False
        cls.failure = None


class FakeIdxContext:
    def __init__(self, config: PbenchServerConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.tracking_id = None
        self.es = None
        self.TS = "FAKE_TS"
        self.templates = FakePbenchTemplates(Path("path"), "test", logger)
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
        dataset: FakeDataset,
        tmpdir: str,
        tarobj: "FakeTarball",
    ):
        self.idxctx = idxctx
        self.tbname = tarobj.controller.name
        self.name = tarobj.name
        self.username = dataset.owner_id
        self.extracted_root = tarobj.cache
        self.index_map = {"root": {"idx1": ["id1", "id2"]}}

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
    tarballs: Dict[OperationName, List[Dataset]] = {}
    called: List[str] = []
    state: Optional[OperationState] = None
    updated: Optional[List[OperationName]] = None
    errors: JSONOBJECT = {}

    @classmethod
    def reset(cls):
        cls.tarballs = {}
        cls.called = []
        cls.state = None
        cls.updated = None
        cls.errors = {}

    def __init__(self, logger: Logger, component: OperationName):
        self.logger = logger
        self.component = component

    def next(self) -> List[Dataset]:
        __class__.called.append(f"next-{self.component.name}")
        assert self.component in __class__.tarballs
        return __class__.tarballs[self.component]

    def update(
        self,
        dataset: Dataset,
        state: Optional[OperationState],
        enabled: Optional[list[OperationName]],
    ):
        __class__.state = state
        __class__.updated = enabled

    def error(self, dataset: Dataset, message: str):
        __class__.errors[dataset.name] = message


class FakeLockRef:
    def __init__(self, lock: Path):
        """Initialize a mocked lock reference

        Args:
            lock: the path of a lock file
        """
        self.locked = False
        self.exclusive = False
        self.unlock = True

    def acquire(self, exclusive: bool = False, wait: bool = True) -> "FakeLockRef":
        """Acquire the lock

        Args:
            exclusive: lock for exclusive access
            wait: [default] wait for lock

        Returns:
            self reference so acquire can be chained with constructor
        """
        self.locked = True
        self.exclusive = exclusive
        return self

    def release(self):
        """Release the lock and close the lock file"""
        self.locked = False
        self.exclusive = False

    def upgrade(self):
        """Upgrade a shared lock to exclusive"""
        if not self.exclusive:
            self.exclusive = True

    def downgrade(self):
        """Downgrade an exclusive lock to shared"""
        if self.exclusive:
            self.exclusive = False


class FakeController:
    def __init__(self, path: Path, cache: Path, logger: Logger):
        self.name = path.name
        self.path = path
        self.cache = cache
        self.logger = logger


class FakeTarball:
    def __init__(self, path: Path, resource_id: str, controller: FakeController):
        self.name = path.name
        self.tarball_path = path
        self.controller = controller
        self.cache = controller.cache / "ABC"
        self.lock = self.cache / "lock"
        self.last_ref = self.cache / "last_ref"
        self.unpacked = self.cache / self.name
        self.isolator = controller.path / resource_id

    def get_results(self, lock: Union[LockRef, LockManager]):
        pass


class FakeCacheManager:
    lookup = {"ABC": "ds1", "ACDF": "ds2", "GHIJ": "ds3"}

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.datasets = {}

    def find_dataset(self, resource_id: str):
        controller = FakeController(Path("/archive/ABC"), Path("/.cache"), self.logger)
        return FakeTarball(
            Path(f"/archive/ABC/{resource_id}/{self.lookup[resource_id]}.tar.xz"),
            resource_id,
            controller,
        )


class FakeAudit:
    BACKGROUND_USER = "test"
    audits: list["FakeAudit"] = []
    sequence: int = 1

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not hasattr(self, "id"):
            self.id = self.sequence
            __class__.sequence += 1

    def as_json(self) -> JSONOBJECT:
        return dict(self.__dict__.items())

    @classmethod
    def create(cls, root: Optional["FakeAudit"] = None, **kwargs) -> "FakeAudit":
        obj = cls(**kwargs)
        if root:
            obj.root = root.id
        cls.audits.append(obj)
        return obj

    @classmethod
    def reset(cls):
        cls.audits.clear()
        cls.sequence = 1


@pytest.fixture()
def mocks(monkeypatch, make_logger):
    FakeDataset.logger = make_logger
    with monkeypatch.context() as m:
        m.setattr("pbench.server.indexing_tarballs.Sync", FakeSync)
        m.setattr("pbench.server.indexing_tarballs.PbenchTarBall", FakePbenchTarBall)
        m.setattr("pbench.server.indexing_tarballs.Report", FakeReport)
        m.setattr("pbench.server.indexing_tarballs.Dataset", FakeDataset)
        m.setattr("pbench.server.indexing_tarballs.Metadata", FakeMetadata)
        m.setattr("pbench.server.indexing_tarballs.IndexMap", FakeIndexMap)
        m.setattr("pbench.server.indexing_tarballs.CacheManager", FakeCacheManager)
        m.setattr("pbench.server.indexing_tarballs.LockRef", FakeLockRef)
        m.setattr("pbench.server.indexing_tarballs.Audit", FakeAudit)
        yield m
    FakeAudit.reset()
    FakeDataset.reset()
    FakeMetadata.reset()
    FakePbenchTemplates.reset()
    FakeReport.reset()
    FakeSync.reset()
    FakePbenchTarBall.reset()


@pytest.fixture()
def index(server_config, make_logger):
    return Index(
        "test",
        Namespace(index_tool_data=False, re_index=False),
        FakeIdxContext(server_config, make_logger),
    )


sizes = {"ds1": 5, "ds2": 2, "ds3": 20}
ds1 = FakeDataset(name="ds1", resource_id="ABC")
ds2 = FakeDataset(name="ds2", resource_id="ACDF")
ds3 = FakeDataset(name="ds3", resource_id="GHIJ")
tarball_1 = TarballData(
    dataset=ds1,
    size=sizes["ds1"],
    tarball=f"{ds1.name}.tar.xz",
)
tarball_2 = TarballData(
    dataset=ds2,
    size=sizes["ds2"],
    tarball=f"{ds2.name}.tar.xz",
)
tarball_3 = TarballData(
    dataset=ds3,
    size=sizes["ds3"],
    tarball=f"{ds3.name}.tar.xz",
)


class TestIndexingTarballs:

    stat_failure: dict[str, Exception] = {}

    @staticmethod
    def mock_stat(file: str) -> stat_result:
        name = Dataset.stem(file)
        if name in __class__.stat_failure:
            raise __class__.stat_failure[name]
        return stat_result([0o777, 123, 300, 1, 100, 100, sizes[name], 0, 0, 0])

    def test_load_templates(self, mocks, index):
        error = index.load_templates()
        assert error == index.error_code["OK"]
        assert FakePbenchTemplates.templates_updated
        assert FakeReport.reported

    def test_load_templates_error(self, mocks, index):
        FakePbenchTemplates.failure = TemplateError("erroneous")
        error = index.load_templates()
        assert error == index.error_code["TEMPLATE_CREATION_ERROR"]
        assert FakePbenchTemplates.templates_updated
        FakePbenchTemplates.reset()

        FakePbenchTemplates.failure = Exception("erroneous")
        error = index.load_templates()
        assert error == index.error_code["GENERIC_ERROR"]
        FakePbenchTemplates.reset()

        FakePbenchTemplates.failure = SigTermException("abort! abort!")
        with pytest.raises(SigTermException):
            index.load_templates()
        assert not FakeReport.reported

    def test_load_templates_report_err(self, mocks, index):
        FakeReport.failure = Exception("I'm a teapot")
        error = index.load_templates()
        assert error == index.error_code["GENERIC_ERROR"]
        assert FakePbenchTemplates.templates_updated
        assert FakeReport.reported

    def test_load_templates_report_abort(self, mocks, index):
        FakeReport.failure = SigTermException("done here")
        with pytest.raises(SigTermException):
            index.load_templates()
        assert FakeReport.reported

    def test_collect_tb_empty(self, mocks, index):
        FakeSync.tarballs[OperationName.INDEX] = []
        tb_list = index.collect_tb()
        assert FakeSync.called == ["next-INDEX"]
        assert tb_list == (0, [])

    def test_collect_tb_missing_tb(self, mocks, index):
        mocks.setattr("pbench.server.indexing_tarballs.os.stat", __class__.mock_stat)
        FakeSync.tarballs[OperationName.INDEX] = [ds1, ds2]
        FakeMetadata.no_tarball = ["ds2"]
        tb_list = index.collect_tb()
        assert FakeSync.called == ["next-INDEX"]
        assert FakeSync.errors["ds2"] == "Dataset does not have a tarball-path"
        assert tb_list == (0, [tarball_1])

    def test_collect_tb_fail(self, mocks, index):
        mocks.setattr("pbench.server.indexing_tarballs.os.stat", __class__.mock_stat)
        __class__.stat_failure = {"ds1": OSError("something wicked that way goes")}
        FakeSync.tarballs[OperationName.INDEX] = [ds1, ds2]
        tb_list = index.collect_tb()
        assert FakeSync.called == ["next-INDEX"]
        assert tb_list == (0, [tarball_2])
        __class__.stat_failure = {}

    def test_collect_tb_exception(self, mocks, index):
        mocks.setattr("pbench.server.indexing_tarballs.os.stat", __class__.mock_stat)
        __class__.stat_failure = {"ds1": Exception("the greater of two weevils")}
        FakeSync.tarballs[OperationName.INDEX] = [ds1, ds2]
        tb_list = index.collect_tb()
        assert FakeSync.called == ["next-INDEX"]
        assert tb_list == (12, [])
        __class__.stat_failure = {}

    def test_collect_tb(self, mocks, index):
        mocks.setattr("pbench.server.indexing_tarballs.os.stat", self.mock_stat)
        FakeSync.tarballs[OperationName.INDEX] = [ds1, ds2]
        tb_list = index.collect_tb()
        assert FakeSync.called == ["next-INDEX"]
        assert tb_list == (0, [tarball_2, tarball_1])

    def test_process_tb_none(self, mocks, index):
        stat = index.process_tb(tarballs=[])
        assert (
            stat == 0
            and not FakePbenchTarBall.make_all_called
            and not FakePbenchTarBall.make_tool_called
        )

    def test_process_tb_bad_load(self, mocks, index):
        FakePbenchTemplates.failure = Exception("I think I can't")
        stat = index.process_tb(tarballs=[])
        assert stat == 12
        assert FakePbenchTemplates.templates_updated

    def test_process_tb_term(self, mocks, index):
        def fake_es_index(es, actions, errorsfp, logger, _dbg=0):
            raise SigTermException("ter-min-ate; ter-min-ate")

        mocks.setattr("pbench.server.indexing_tarballs.es_index", fake_es_index)
        stat = index.process_tb(tarballs=[tarball_2, tarball_1])
        assert stat == 0

    def test_process_tb_interrupt(self, mocks, index):
        def fake_es_index(es, actions, errorsfp, logger, _dbg=0):
            raise SigIntException("cease. also desist. and stop. that too.")

        mocks.setattr("pbench.server.indexing_tarballs.es_index", fake_es_index)
        stat = index.process_tb(tarballs=[tarball_2, tarball_1])
        assert stat == 0

    def test_process_tb_int(self, mocks, index):
        """Test behavior when a SIGHUP occurs during processing.

        This should trigger the indexer to re-evaluate the set of enabled
        datasets after completing the current dataset. Because the mock
        here generates a SIGHUP on the first index operation any additional
        enabled datasets would be missed unless they're still enabled and
        are reported by the subsequent collect_tb() call. The verified action
        sequence here confirms that the second (skipped) dataset in the
        initial parameter list (tarball_1) is only indexed once despite also
        appearing in the SIGHUP collect_tb.
        """
        index_actions = []
        first_index = True

        def fake_es_index(es, actions, errorsfp, logger, _dbg=0):
            nonlocal first_index
            if first_index:
                first_index = False
                os.kill(os.getpid(), SIGHUP)
            index_actions.append(actions)
            return (1000, 2000, 1, 0, 0, 0)

        mocks.setattr("pbench.server.indexing_tarballs.es_index", fake_es_index)
        mocks.setattr(Index, "collect_tb", lambda self: (0, [tarball_1, tarball_3]))
        stat = index.process_tb(tarballs=[tarball_2, tarball_1])
        assert (
            stat == 0
            and FakePbenchTarBall.make_all_called == 3
            and not FakePbenchTarBall.make_tool_called
        )
        assert index_actions == [
            [{"action": "make_all_actions", "name": f"{ds2.name}.tar.xz"}],
            [{"action": "make_all_actions", "name": f"{ds1.name}.tar.xz"}],
            [{"action": "make_all_actions", "name": f"{ds3.name}.tar.xz"}],
        ]

    def test_process_tb_merge(self, mocks, index):
        def fake_es_index(es, actions, errorsfp, logger, _dbg=0):
            return (1000, 2000, 1, 0, 0, 0)

        FakeIndexMap.index_map = {
            "ds1": {
                "root": {"idx3": ["id3", "id4"], "idx1": ["id4"]},
                "r1": {"idx": ["a", "b"]},
            }
        }
        mocks.setattr("pbench.server.indexing_tarballs.es_index", fake_es_index)
        stat = index.process_tb(tarballs=[tarball_1])
        assert (
            stat == 0
            and FakePbenchTarBall.make_all_called == 1
            and not FakePbenchTarBall.make_tool_called
        )
        assert FakeIndexMap.index_map == {
            "ds1": {
                "root": {"idx1": ["id4", "id1", "id2"], "idx3": ["id3", "id4"]},
                "r1": {"idx": ["a", "b"]},
            }
        }

    def test_process_tb(self, mocks, index):
        index_actions = []

        def fake_es_index(es, actions, errorsfp, logger, _dbg=0):
            index_actions.append(actions)
            return (1000, 2000, 1, 0, 0, 0)

        mocks.setattr("pbench.server.indexing_tarballs.es_index", fake_es_index)
        stat = index.process_tb(tarballs=[tarball_2, tarball_1])
        assert (
            stat == 0
            and FakePbenchTarBall.make_all_called == 2
            and not FakePbenchTarBall.make_tool_called
        )
        assert index_actions == [
            [{"action": "make_all_actions", "name": f"{ds2.name}.tar.xz"}],
            [{"action": "make_all_actions", "name": f"{ds1.name}.tar.xz"}],
        ]
        assert [a.as_json() for a in FakeAudit.audits] == [
            {
                "dataset": ds2,
                "id": 1,
                "name": "index",
                "operation": OperationCode.UPDATE,
                "status": AuditStatus.BEGIN,
                "user_name": "test",
            },
            {"attributes": None, "id": 2, "root": 1, "status": AuditStatus.SUCCESS},
            {
                "dataset": ds1,
                "id": 3,
                "name": "index",
                "operation": OperationCode.UPDATE,
                "status": AuditStatus.BEGIN,
                "user_name": "test",
            },
            {"attributes": None, "id": 4, "root": 3, "status": AuditStatus.SUCCESS},
        ]
