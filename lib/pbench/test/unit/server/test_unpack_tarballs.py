from dataclasses import dataclass
import datetime
from logging import Logger
from pathlib import Path
from typing import Optional, Union

import pytest

from pbench.client import JSON, JSONOBJECT
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.cache_manager import TarballUnpackError
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.users import User
from pbench.server.sync import Operation
from pbench.server.unpack_tarballs import UnpackTarballs


@pytest.fixture()
def make_logger(server_config):
    """
    Construct a Pbench Logger object
    """
    return get_pbench_logger("TEST", server_config)


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

    def __init__(self, logger: Logger, component: str):
        self.component = component
        self.logger = logger

    def next(self, operation: Operation) -> list[Dataset]:
        return [x.dataset for x in datasets]

    def update(self, dataset: Dataset, did: Operation, enabled: list[Operation]):
        assert dataset.resource_id not in __class__.record
        __class__.record[dataset.resource_id] = {"did": did, "enabled": enabled}

    @classmethod
    def _reset(cls):
        cls.record = {}


class FakePbenchTemplates:
    templates_updated = False
    failure: Optional[Exception] = None

    def __init__(self, basepath, idx_prefix, logger, known_tool_handlers=None, _dbg=0):
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

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        self.config = config
        self.logger = logger

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
    def test_buckets(self, mocks, make_logger, min_size, max_size, targets):
        """Test that the tarbal list is filtered by the unpack bucket size
        configuration."""

        obj = UnpackTarballs(MockConfig(), make_logger)
        result = obj.unpack_tarballs(min_size, max_size)
        assert result.total == len(targets)
        assert result.success == len(targets)
        assert sorted(MockCacheManager.unpacked) == sorted(targets)
        assert sorted(MockSync.record.keys()) == sorted(targets)
        for actions in MockSync.record.values():
            assert actions["did"] == Operation.UNPACK
            assert actions["enabled"] == [Operation.COPY_SOS, Operation.INDEX]

    @pytest.mark.parametrize(
        "fail", [["md5.1"], ["md5.1", "md5.2"], ["md5.1", "md5.2", "md5.3"]]
    )
    def test_failures(self, make_logger, fail, mocks):
        """Test that tarball evaluation continues when resolution of one or
        more fails."""

        obj = UnpackTarballs(MockConfig(), make_logger)
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
    def test_unpack_exception(self, make_logger, mocks, fail):
        """Show that when unpack module raises TarballUnpackError exception
        it is being handled properly."""

        obj = UnpackTarballs(MockConfig, make_logger)
        MockCacheManager._fail_on(fail)

        # FIXME [PBENCH-961] The unpack_tarballs loop should handle unpack
        # exceptions and continue with the loop without exposing the exception
        # to the caller. When this bug is fixed, remote `with pytest.raises`
        # here and dedent the following code, which is analogous to the above
        # test_failures case for Path errors.
        with pytest.raises(TarballUnpackError):
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

    def test_unpack_report(self, make_logger, mocks):
        obj = UnpackTarballs(MockConfig, make_logger)
        obj.report("done", "done done")
        assert FakeReport.reported
        assert FakeReport.inited
