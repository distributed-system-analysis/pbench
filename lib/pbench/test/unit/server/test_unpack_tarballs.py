from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Union

import pytest

from pbench.client import JSONOBJECT
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.cache_manager import TarballUnpackError
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.sync import Operation
from pbench.server.unpack_tarballs import Target, UnpackTarballs


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
    TarballInfo(Dataset(resource_id="md5.2", name="d2"), "/pb/ar/xy/d2.tar.xz", 500),
    TarballInfo(Dataset(resource_id="md5.3", name="d3"), "/pb/ar/xy/d3.tar.xz", 900),
]


def getvalue(dataset: Dataset, key: str):
    for d in datasets:
        if d.dataset.resource_id == dataset.resource_id:
            return d.tarball
    return None


class MockConfig:
    ARCHIVE = Path("/mock/ARCHIVE")
    INCOMING = Path("/mock/INCOMING")
    RESULTS = Path("/mock/RESULTS")
    TS = "my_timestamp"

    def get(section: str, option: str, fallback=None) -> str:
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

    def resolve(self, strict: bool = False):
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
        __class__.record[dataset.resource_id] = {"did": did, "enabled": enabled}

    @classmethod
    def _reset(cls):
        cls.record = {}


class MockCacheManager:

    fails: list[str] = []
    unpacked: list[str] = []

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        self.config = config
        self.logger = logger

    def unpack(self, id: str):
        if id in __class__.fails:
            for d in datasets:
                if d.dataset.resource_id == id:
                    raise TarballUnpackError(Path(d.tarball), "test error")
            else:
                raise Exception("I'm lost; where are you?")
        __class__.unpacked.append(id)

    @classmethod
    def _fail_on(cls, fails: list[str]):
        cls.fails.extend(fails)

    @classmethod
    def _reset(cls):
        cls.fails.clear()
        cls.unpacked.clear()


class TestUnpackTarballs:
    @pytest.fixture()
    def reset(self):
        MockPath._reset()
        MockSync._reset()
        MockCacheManager._reset()

    @pytest.mark.parametrize(
        "min_size,max_size,targets",
        [
            (586, 1000, ["md5.3"]),
            (0, 1000, ["md5.1", "md5.2", "md5.3"]),
            (0, 586, ["md5.1", "md5.2"]),
        ],
    )
    def test_buckets(
        self, monkeypatch, make_logger, reset, min_size, max_size, targets
    ):
        """Test that the tarbal list is filtered by the unpack bucket size
        configuration."""

        with monkeypatch.context() as m:
            m.setattr("pbench.server.unpack_tarballs.Path", MockPath)
            m.setattr("pbench.server.unpack_tarballs.Sync", MockSync)
            m.setattr("pbench.server.unpack_tarballs.CacheManager", MockCacheManager)
            m.setattr(Metadata, "getvalue", getvalue)

            obj = UnpackTarballs(MockConfig(), make_logger)
            result = obj.unpack_tarballs(min_size, max_size)
            assert result.total == len(targets)
            assert result.success == len(targets)
            assert sorted(MockCacheManager.unpacked) == sorted(targets)
            assert sorted(MockSync.record.keys()) == sorted(targets)
            for id, actions in MockSync.record.items():
                assert actions["did"] == Operation.UNPACK
                assert actions["enabled"] == [Operation.COPY_SOS, Operation.INDEX]

    @pytest.mark.parametrize("fail", [["md5.1"], ["md5.1", "md5.2"], []])
    def test_failures(self, monkeypatch, make_logger, fail, reset):
        """Test that tarball evaluation continues when resolution of one or
        more fails."""

        with monkeypatch.context() as m:
            m.setattr("pbench.server.unpack_tarballs.Path", MockPath)
            m.setattr("pbench.server.unpack_tarballs.Sync", MockSync)
            m.setattr("pbench.server.unpack_tarballs.CacheManager", MockCacheManager)
            m.setattr(Metadata, "getvalue", getvalue)

            obj = UnpackTarballs(MockConfig(), make_logger)
            MockPath._fail_on(fail)
            result = obj.unpack_tarballs(0.0, 1000.0)
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

    def test_unpack_exception(self, monkeypatch, make_logger, reset):
        """Show that when unpack module raises TarballUnpackError exception
        it is being handled properly."""

        with monkeypatch.context() as m:
            m.setattr("pbench.server.unpack_tarballs.Path", MockPath)
            m.setattr("pbench.server.unpack_tarballs.Sync", MockSync)
            m.setattr("pbench.server.unpack_tarballs.CacheManager", MockCacheManager)
            m.setattr(Metadata, "getvalue", getvalue)
            obj = UnpackTarballs(MockConfig, make_logger)
            tar = MockPath(datasets[0].tarball)
            target = Target(datasets[0].dataset, tar)
            MockCacheManager._fail_on([datasets[0].dataset.resource_id])
            with pytest.raises(TarballUnpackError):
                obj.unpack(target)
