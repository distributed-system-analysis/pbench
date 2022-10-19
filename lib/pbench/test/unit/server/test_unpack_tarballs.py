from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Union

import pytest

from pbench.client import JSONOBJECT
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.cache_manager import CacheManager, TarballUnpackError
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
            def unpack(self, dataset_id: str):
                """Mock of CacheManager.unpack(tar_md5) function"""
                mocks_called.append("unpack")

    fails: list[str] = []
    unpacked: list[str] = []

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        self.config = config
        self.logger = logger

    def test_unpack_symlinks_creation(self, monkeypatch, make_logger, caplog):
        """Show that when symlink creation fails and raises
        FileNotFoundError Exception it is handled successfully."""
        mocks_called = []

    @classmethod
    def _fail_on(cls, fails: list[str]):
        cls.fails.append(fails)

    @classmethod
    def _reset(cls):
        cls.fails.clear()
        cls.unpacked.clear()


class TestUnpackTarballs:
    @pytest.fixture()
    def reset(self):
        MockPath._reset()
        MockSync._reset()
        MockFileTree._reset()

    def test_unpack_symlinks_removal(self, monkeypatch, make_logger, caplog):
        """Show that, when unlinking the tarball results in
        a FileNotFoundError, it is handled successfully."""
        mocks_called = []

        def tickmock(id: str, ret_val: Any) -> Any:
            mocks_called.append(id)
            return ret_val

        def mock_unlink(path):
            """
            Mock of os.unlink() function

            Args:
                path: tarball path in 'TO-INDEX' state directory

            Returns:
                Raises FileNotFoundError Exception
            """
            mocks_called.append("mock_unlink")
            raise FileNotFoundError(f"No such file or directory: '{path}'")

        monkeypatch.setattr(os, "symlink", lambda path, dest: tickmock("symlink", None))
        monkeypatch.setattr(os, "unlink", mock_unlink)
        obj = UnpackTarballs(MockConfig, make_logger)
        with pytest.raises(FileNotFoundError):
            obj.update_symlink(self.tar)
            assert (
                f"Error in removing symlink from TO-UNPACK state. No such file or directory: '{MockConfig.ARCHIVE / 'ABC' / obj.LINKSRC / self.tar.name}'"
                in caplog.text
            )
        assert mocks_called == ["symlink", "symlink", "mock_unlink"]

    def test_unpack_symlinks_success(self, monkeypatch, make_logger):
        """Show that the symlinks are updated and removed successfully."""
        mocks_called = []

        def tickmock(id: str, ret_val: Any) -> Any:
            mocks_called.append(id)
            return ret_val

        monkeypatch.setattr(os, "symlink", lambda path, dest: tickmock("symlink", None))
        monkeypatch.setattr(os, "unlink", lambda path: tickmock("unlink", None))
        obj = UnpackTarballs(MockConfig, make_logger)
        obj.update_symlink(self.tar)
        assert mocks_called == ["symlink", "symlink", "unlink"]

    def test_unpack_tarballs_unpack_failure(self, monkeypatch, make_logger):
        """Show that when unpacking failure leads to TarballUnpackError,
        it is handled successfully."""

        mocks_called = []

        def tickmock(id: str, ret_val: Any) -> Any:
            mocks_called.append(id)
            return ret_val

        def mock_unpack(self, tb, cache_m):
            """
            Mock of UnpackTarballs.unpack(self.min_size, self.max_size) function

            obj = UnpackTarballs(MockConfig(), make_logger)
            result = obj.unpack_tarballs(min_size, max_size)
            assert result.total == len(targets)
            assert result.success == len(targets)
            assert sorted(MockFileTree.unpacked) == sorted(targets)
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
            m.setattr("pbench.server.unpack_tarballs.FileTree", MockFileTree)
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
            assert sorted(MockFileTree.unpacked) == ids
            assert sorted(MockSync.record.keys()) == ids

    def test_unpack_exception(self, monkeypatch, make_logger, reset):
        """Show that when unpack module raises TarballUnpackError exception
        it is being handled properly."""

        with monkeypatch.context() as m:
            m.setattr("pbench.server.unpack_tarballs.Path", MockPath)
            m.setattr("pbench.server.unpack_tarballs.Sync", MockSync)
            m.setattr("pbench.server.unpack_tarballs.FileTree", MockFileTree)
            m.setattr(Metadata, "getvalue", getvalue)
            obj = UnpackTarballs(MockConfig, make_logger)
            tar = MockPath(datasets[0].tarball)
            target = Target(datasets[0].dataset, tar)
            MockFileTree.fails.append(datasets[0].dataset.resource_id)
            with pytest.raises(TarballUnpackError):
                obj.unpack(target)
