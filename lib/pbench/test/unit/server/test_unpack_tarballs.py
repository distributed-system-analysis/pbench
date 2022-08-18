from collections import namedtuple
import os
from pathlib import Path
from typing import Any

import pytest

from pbench.common.logger import get_pbench_logger
from pbench.server.filetree import FileTree, TarballUnpackError
from pbench.server.unpack_tarballs import UnpackTarballs


@pytest.fixture()
def make_logger(server_config):
    """
    Construct a Pbench Logger object
    """
    return get_pbench_logger("TEST", server_config)


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


class TestUnpackTarballs:
    tarlist = ["/mock/ABC/TO-UNPACK/A.tar.xz", "/mock/ABC/TO-UNPACK/B.tar.xz"]
    tar = Path(tarlist[0])
    min_size, max_size = 0, 1000
    tar_size, tar_mode = 586, 16893

    def mock_stat(self, *args, follow_symlinks=False):
        """Mocked replacement for Path.stat()"""
        StatResult = namedtuple("StatResult", ["st_mode", "st_size"])
        return StatResult(
            st_mode=TestUnpackTarballs.tar_mode, st_size=TestUnpackTarballs.tar_size
        )

    @pytest.mark.parametrize(
        "min_size, max_size, total", [(586, 1000, 2), (0, 1000, 2), (0, 586, 0)]
    )
    def test_tarball_size(
        self, monkeypatch, make_logger, caplog, min_size, max_size, total
    ):
        """Test for the valid size and path of the tarball. We are intentionally
        causing Path.resolve() to fail as a means to short-circuit the CUT
        while still enabling the testing of the size filtering."""

        def mock_resolve(self: Path, strict: bool = False):
            """
            Mock replacement for Path.resolve()

            Args:
                strict: Boolean value to make sure path exist if True.

            Returns:
                Raising FileNotFoundError Exception
            """
            assert strict
            raise FileNotFoundError(f"No such file or directory: '{self}'")

        monkeypatch.setattr(Path, "glob", lambda path, args: self.tarlist)
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        monkeypatch.setattr(Path, "stat", self.mock_stat)
        obj = UnpackTarballs(MockConfig, make_logger)
        result = obj.unpack_tarballs(min_size, max_size)
        if result.total > 0:
            for tar in self.tarlist:
                assert (
                    f"Tarball link, '{tar}', does not resolve to a real location: No such file or directory: '{tar}'"
                    in caplog.text
                )
        assert result.total == total
        assert result.success == 0

    def test_unpack_md5_error(self, monkeypatch, make_logger, caplog):
        """Show that when md5 file path cannot be accessed it throws a
        FileNotFoundError Exception"""

        mocks_called = []

        def mock_md5sum(filepath: Path):
            """
            Mock of md5sum function

            Args:
                filepath: Tarball file path

            Returns:
                Raises FileNotFoundError Exception
            """
            mocks_called.append("mock_tarball_md5")
            raise FileNotFoundError(f"No such file or directory: '{filepath}.md5'")

        monkeypatch.setattr("pbench.server.utils.md5sum", mock_md5sum)
        obj = UnpackTarballs(MockConfig, make_logger)
        with pytest.raises(FileNotFoundError):
            obj.unpack(self.tar, None)
            assert (
                f"Getting md5 value of tarball '{self.tar}' failed: No such file or directory: '{self.tar}.md5'"
                in caplog.text
            )
        assert mocks_called == ["mock_tarball_md5"]

    def test_unpack_exception(self, monkeypatch, make_logger, caplog):
        """Show that when unpack module raises TarballUnpackError exception
        it is being handled properly."""
        mocks_called = []

        def tickmock(id: str, ret_val: Any) -> Any:
            mocks_called.append(id)
            return ret_val

        class MockFileTree:
            def unpack(self, dataset_id: str):
                """Mock of FileTree.unpack(tar_md5) function"""
                mocks_called.append("mock_unpack")
                raise TarballUnpackError("tarball", "tar exited with status 1")

        monkeypatch.setattr(
            "pbench.server.unpack_tarballs.get_tarball_md5",
            lambda tb: tickmock("tarball_md5", "my_md5_string"),
        )
        obj = UnpackTarballs(MockConfig, make_logger)
        with pytest.raises(TarballUnpackError):
            obj.unpack(self.tar, MockFileTree())
            assert (
                f"Unpacking of tarball {self.tar} failed: An error occurred while unpacking tarball: tar exited with status 1"
                in caplog.text
            )
        assert mocks_called == ["tarball_md5", "mock_unpack"]

    def test_unpack_success(self, monkeypatch, make_logger):
        """Show that the unpacking of Tarballs proceeds successfully."""
        mocks_called = []

        class MockFileTree:
            def unpack(self, dataset_id: str):
                """Mock of FileTree.unpack(tar_md5) function"""
                mocks_called.append("unpack")

        def tickmock(id: str, ret_val: Any) -> Any:
            mocks_called.append(id)
            return ret_val

        monkeypatch.setattr(
            "pbench.server.unpack_tarballs.get_tarball_md5",
            lambda tb: tickmock("tarball_md5", "my_md5_string"),
        )
        obj = UnpackTarballs(MockConfig, make_logger)
        obj.unpack(self.tar, MockFileTree())
        assert mocks_called == ["tarball_md5", "unpack"]

    def test_unpack_symlinks_creation(self, monkeypatch, make_logger, caplog):
        """Show that when symlink creation fails and raises
        FileNotFoundError Exception it is handled successfully."""
        mocks_called = []

        def mock_symlink(path: Path, dest: Path):
            """
            Mock of os.symlink() function

            Args:
                path: tarball file path
                dest: destination path to create symlink

            Returns:
                Raises FileNotFoundError Exception
            """
            mocks_called.append("mock_symlink")
            raise FileNotFoundError(f"'{path}' -> '{dest}'")

        linkedlistdest = MockConfig.get("pbench-server", "unpacked-states").split(", ")[
            0
        ]
        monkeypatch.setattr(os, "symlink", mock_symlink)
        obj = UnpackTarballs(MockConfig, make_logger)
        with pytest.raises(FileNotFoundError):
            obj.update_symlink(self.tar)
            assert (
                f"Error in creation of symlink. '{MockConfig.ARCHIVE / 'ABC' / self.tar.name}' -> '{MockConfig.ARCHIVE / 'ABC' / linkedlistdest / self.tar.name}'"
                in caplog.text
            )
        assert mocks_called == ["mock_symlink"]

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

        def mock_unpack(self, tb, file_tree):
            """
            Mock of UnpackTarballs.unpack(self.min_size, self.max_size) function

            Args:
                dataset_id: tarball md5 value

            Returns:
                Raises TarballUnpackError Exception
            """
            mocks_called.append("mock_unpack")
            raise TarballUnpackError("tarball", "tar exited with status 1")

        def mock_update_symlink(self, tb):
            """Mock of update_symlink() function"""
            mocks_called.append("mock_symlink")

        monkeypatch.setattr(
            Path, "glob", lambda path, args: tickmock("glob", self.tarlist)
        )
        monkeypatch.setattr(
            Path, "resolve", lambda path, strict: tickmock("resolve", self)
        )
        monkeypatch.setattr(
            FileTree,
            "__init__",
            lambda self, config, logger: tickmock("filetree", None),
        )
        monkeypatch.setattr(
            Path,
            "stat",
            lambda self, *args, **kwargs: tickmock(
                "stat", TestUnpackTarballs.mock_stat(self, *args, **kwargs)
            ),
        )
        monkeypatch.setattr(UnpackTarballs, "unpack", mock_unpack)
        monkeypatch.setattr(UnpackTarballs, "update_symlink", mock_update_symlink)
        obj = UnpackTarballs(MockConfig, make_logger)
        result = obj.unpack_tarballs(self.min_size, self.max_size)
        assert mocks_called == [
            "glob",
            "stat",
            "stat",
            "filetree",
            "resolve",
            "mock_unpack",
            "resolve",
            "mock_unpack",
        ]
        assert result.total == 2
        assert result.success == 0

    def test_unpack_tarballs_symlink_failure(self, monkeypatch, make_logger):
        """Show that when unlinking failure leads to FileNotFoundError,
        it is handled successfully."""
        mocks_called = []

        def tickmock(id: str, ret_val: Any) -> Any:
            mocks_called.append(id)
            return ret_val

        def mock_update_symlink(self, path):
            """
            Mock of update_symlink() function

            Args:
                path: tarball path in 'TO-INDEX' state directory

            Returns:
                Raises FileNotFoundError Exception
            """
            mocks_called.append("mock_update_symlink")
            raise FileNotFoundError(f"No such file or directory: '{path}'")

        monkeypatch.setattr(
            Path, "glob", lambda path, args: tickmock("glob", self.tarlist)
        )
        monkeypatch.setattr(
            Path, "resolve", lambda path, strict: tickmock("resolve", self)
        )
        monkeypatch.setattr(
            FileTree,
            "__init__",
            lambda self, config, logger: tickmock("filetree", None),
        )
        monkeypatch.setattr(
            Path,
            "stat",
            lambda self, *args, **kwargs: tickmock(
                "stat", TestUnpackTarballs.mock_stat(self, *args, **kwargs)
            ),
        )
        monkeypatch.setattr(
            UnpackTarballs, "unpack", lambda self, *args: tickmock("unpack", None)
        )
        monkeypatch.setattr(UnpackTarballs, "update_symlink", mock_update_symlink)
        obj = UnpackTarballs(MockConfig, make_logger)
        result = obj.unpack_tarballs(self.min_size, self.max_size)
        assert mocks_called == [
            "glob",
            "stat",
            "stat",
            "filetree",
            "resolve",
            "unpack",
            "mock_update_symlink",
            "resolve",
            "unpack",
            "mock_update_symlink",
        ]
        assert result.total == 2
        assert result.success == 0

    def test_unpack_tarballs_success(self, monkeypatch, make_logger):
        """Show that when unpacking goes smoothly we can count the
        successfully unpacked tarballs."""
        mocks_called = []

        def tickmock(id: str, ret_val: Any) -> Any:
            mocks_called.append(id)
            return ret_val

        monkeypatch.setattr(
            Path, "glob", lambda path, args: tickmock("glob", self.tarlist)
        )
        monkeypatch.setattr(
            Path,
            "stat",
            lambda self, *args, **kwargs: tickmock(
                "stat", TestUnpackTarballs.mock_stat(self, *args, **kwargs)
            ),
        )
        monkeypatch.setattr(
            Path, "resolve", lambda path, strict: tickmock("resolve", self)
        )
        monkeypatch.setattr(
            FileTree,
            "__init__",
            lambda self, config, logger: tickmock("filetree", None),
        )
        monkeypatch.setattr(
            UnpackTarballs, "unpack", lambda self, *args: tickmock("unpack", None)
        )
        monkeypatch.setattr(
            UnpackTarballs,
            "update_symlink",
            lambda path, *args: tickmock("update_symlink", None),
        )
        obj = UnpackTarballs(MockConfig, make_logger)
        result = obj.unpack_tarballs(self.min_size, self.max_size)
        assert mocks_called == [
            "glob",
            "stat",
            "stat",
            "filetree",
            "resolve",
            "unpack",
            "update_symlink",
            "resolve",
            "unpack",
            "update_symlink",
        ]
        assert result.total == 2
        assert result.success == 2
