from dataclasses import dataclass
import datetime
from pathlib import Path
from typing import Optional, Union

import pytest

from pbench.server import JSON, JSONOBJECT
from pbench.server.cache_manager import TarballUnpackError
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    OperationName,
    OperationState,
)
from pbench.server.database.models.users import User
from pbench.server.unpack_tarballs import UnpackTarballs


@dataclass(frozen=True)
class TarballInfo:
    dataset: Dataset
    tarball: str
    size: int


datasets = [
    TarballInfo(Dataset(resource_id="md5.1", name="d1"), "/pb/ar/xy/d1.tar.xz", 250),
    TarballInfo(Dataset(resource_id="md5.2", name="d2"), "/pb/ar/xy/d2.tar.xz", 586),
    TarballInfo(Dataset(resource_id="md5.3", name="d3"), "/pb/ar/xy/d3.tar.xz", 900),
]


def getvalue(dataset: Dataset, key: str, user: Optional[User] = None) -> Optional[JSON]:
    for d in datasets:
        if d.dataset.resource_id == dataset.resource_id:
            return d.tarball
    return None


class MockConfig:
    ARCHIVE = Path("/mock/ARCHIVE")
    INCOMING = Path("/mock/INCOMING")
    RESULTS = Path("/mock/RESULTS")
    PBENCH_ENV = "pbench"
    TMP = "/tmp"
    TS = "my_timestamp"
    timestamp = datetime.datetime.now

    def get(self, section: str, option: str, fallback=None) -> str:
        """returns value of the given `section` and `option`"""

        assert section == "pbench-server"
        assert option == "unpacked-states"
        return "TO-INDEX, TO-COPY-SOS"


@dataclass()
class StatResult:
    st_mode: int
    st_size: int


class MockPath:

    fails: list[str] = []

    def __init__(self, path: Union[str, Path, "MockPath"]):
        self.path = str(path)
        self.name = Path(path).name

    def resolve(self, strict: bool = False) -> "MockPath":
        assert strict
        for t in datasets:
            if self.path == t.tarball:
                if t.dataset.resource_id in __class__.fails:
                    break  # Drop out to raise an exception
                return MockPath(self.path)
        raise FileNotFoundError(f"No such file or directory: '{self.path}'")

    def stat(self) -> StatResult:
        for t in datasets:
            if self.path == t.tarball:
                return StatResult(st_mode=0o554, st_size=t.size)
        raise FileNotFoundError(f"No such file or directory: '{self.path}'")

    def __fspath__(self) -> str:
        return self.path

    def __str__(self) -> str:
        return self.path

    @classmethod
    def _fail_on(cls, fails: list[str]):
        cls.fails.extend(fails)

    @classmethod
    def _reset(cls):
        cls.fails.clear()


class MockSync:

    record: dict[str, JSONOBJECT] = {}
    errors: dict[str, JSONOBJECT] = {}

    def __init__(self, component: OperationName):
        self.component = component

    def next(self) -> list[Dataset]:
        return [x.dataset for x in datasets]

    def update(
        self, dataset: Dataset, state: OperationState, enabled: list[OperationName]
    ):
        assert dataset.resource_id not in __class__.record
        __class__.record[dataset.resource_id] = {
            "component": self.component,
            "state": state,
            "enabled": enabled,
        }

    def error(self, dataset: Dataset, message: str):
        __class__.errors[dataset.resource_id] = {
            "component": self.component,
            "message": message,
        }

    @classmethod
    def _reset(cls):
        cls.record = {}
        cls.errors = {}


class FakePbenchTemplates:
    templates_updated = False
    failure: Optional[Exception] = None

    def __init__(self, basepath, idx_prefix, known_tool_handlers=None, _dbg=0):
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
    inited = False
    failure: Optional[Exception] = None

    def __init__(
        self,
        name,
        es=None,
        pid=None,
        group_id=None,
        user_id=None,
        hostname=None,
        version=None,
        templates=None,
    ):
        self.name = name

    def post_status(
        self, timestamp: str, doctype: str, file_to_index: Optional[Path] = None
    ) -> str:
        __class__.reported = True
        if self.failure:
            raise self.failure
        return "tracking_id"

    def init_report_template(self):
        __class__.inited = True

    @classmethod
    def reset(cls):
        cls.reported = False
        cls.inited = False
        cls.failure = None


class MockCacheManager:

    fails: list[str] = []
    unpacked: list[str] = []

    def __init__(self):
        pass

    def unpack(self, id: str):
        if id in __class__.fails:
            assert id in [d.dataset.resource_id for d in datasets]
            for d in datasets:
                if d.dataset.resource_id == id:
                    raise TarballUnpackError(Path(d.tarball), "test error")
        __class__.unpacked.append(id)

    @classmethod
    def _fail_on(cls, fails: list[str]):
        cls.fails.extend(fails)

    @classmethod
    def _reset(cls):
        cls.fails.clear()
        cls.unpacked.clear()


@pytest.fixture()
def mocks(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr("pbench.server.unpack_tarballs.Sync", MockSync)
        m.setattr("pbench.server.unpack_tarballs.Path", MockPath)
        m.setattr("pbench.server.unpack_tarballs.Report", FakeReport)
        m.setattr("pbench.server.unpack_tarballs.CacheManager", MockCacheManager)
        m.setattr(Metadata, "getvalue", getvalue)
        yield m
    FakePbenchTemplates.reset()
    FakeReport.reset()
    MockPath._reset()
    MockSync._reset()
    MockCacheManager._reset()


class TestUnpackTarballs:
    @pytest.mark.parametrize(
        "min_size,max_size,targets",
        [
            (586, 900, ["md5.2"]),  # min >= x < max
            (250, 901, ["md5.1", "md5.2", "md5.3"]),
            (0, 900, ["md5.1", "md5.2"]),  # upper is strict <
        ],
    )
    def test_buckets(self, mocks, server_logger, min_size, max_size, targets):
        """Test that the tarbal list is filtered by the unpack bucket size
        configuration."""

        obj = UnpackTarballs()
        result = obj.unpack_tarballs(min_size, max_size)
        assert result.total == len(targets)
        assert result.success == len(targets)
        assert sorted(MockCacheManager.unpacked) == sorted(targets)
        assert sorted(MockSync.record.keys()) == sorted(targets)
        for actions in MockSync.record.values():
            assert actions["component"] == OperationName.UNPACK
            assert actions["state"] == OperationState.OK
            assert actions["enabled"] == [OperationName.INDEX]

    @pytest.mark.parametrize(
        "fail", [["md5.1"], ["md5.1", "md5.2"], ["md5.1", "md5.2", "md5.3"]]
    )
    def test_failures(self, server_logger, fail, mocks):
        """Test that tarball evaluation continues when resolution of one or
        more fails."""

        obj = UnpackTarballs()
        MockPath._fail_on(fail)
        result = obj.unpack_tarballs(0.0, float("inf"))
        assert result.total == len(datasets) - len(fail)
        assert result.success == result.total
        ids = sorted(
            [
                t.dataset.resource_id
                for t in datasets
                if t.dataset.resource_id not in fail
            ]
        )
        assert sorted(MockCacheManager.unpacked) == ids
        assert sorted(MockSync.record.keys()) == ids

    @pytest.mark.parametrize(
        "fail", [["md5.1"], ["md5.2"], ["md5.3"], ["md5.1", "md5.2", "md5.3"]]
    )
    def test_unpack_exception(self, server_logger, mocks, fail):
        """Show that when unpack module raises TarballUnpackError exception
        it is being handled properly."""

        obj = UnpackTarballs()
        MockCacheManager._fail_on(fail)

        result = obj.unpack_tarballs(0.0, float("inf"))
        assert result.success == len(datasets) - len(fail)
        assert result.total == len(datasets)
        success_ids = []
        fail_ids = []
        for t in datasets:
            id = t.dataset.resource_id
            if id in fail:
                fail_ids.append(id)
            else:
                success_ids.append(id)
        success_ids.sort()
        fail_ids.sort()
        assert sorted(MockCacheManager.unpacked) == success_ids
        assert sorted(MockSync.record.keys()) == success_ids
        assert sorted(MockSync.errors.keys()) == fail_ids

    def test_unpack_report(self, server_logger, mocks):
        obj = UnpackTarballs()
        obj.report("done", "done done")
        assert FakeReport.reported
        assert FakeReport.inited
