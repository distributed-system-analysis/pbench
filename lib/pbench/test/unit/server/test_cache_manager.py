from contextlib import contextmanager
import errno
import fcntl
import hashlib
import io
from logging import Logger
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Optional

import pytest

from pbench.server import JSONOBJECT
from pbench.server.cache_manager import (
    BadDirpath,
    BadFilename,
    CacheExtractBadPath,
    CacheManager,
    CacheType,
    Controller,
    DuplicateTarball,
    Inventory,
    MetadataError,
    Tarball,
    TarballModeChangeError,
    TarballNotFound,
    TarballUnpackError,
)
from pbench.server.database.models.datasets import Dataset, DatasetBadName
from pbench.test.unit.server.conftest import make_tarball


@pytest.fixture(scope="function", autouse=True)
def file_sweeper(server_config):
    """
    Make sure that the required directory trees exist before each test case,
    and clean up afterwards.
    """
    trees = [server_config.ARCHIVE, server_config.CACHE]

    for tree in trees:
        tree.mkdir(parents=True, exist_ok=True)

    yield

    # After each test case, remove the contents of each of the root tree
    # directories.

    for tree in trees:
        for file in tree.iterdir():
            if file.is_dir():
                shutil.rmtree(file, ignore_errors=True)
            else:
                file.unlink()


@pytest.fixture()
def selinux_disabled(monkeypatch):
    """
    Pretend that selinux is disabled so restorecon isn't called
    """
    monkeypatch.setattr("pbench.common.selinux.is_selinux_enabled", lambda: 0)


@pytest.fixture()
def selinux_enabled(monkeypatch):
    """
    Pretend that selinux is enabled but make restorecon exit with no action
    """
    monkeypatch.setattr("pbench.common.selinux.is_selinux_enabled", lambda: 1)
    monkeypatch.setattr("pbench.common.selinux.restorecon", lambda a: None)


def fake_get_metadata(_tb_path):
    return {"pbench": {"date": "2002-05-16T00:00:00"}, "run": {"controller": "ABC"}}


MEMBER_NOT_FOUND_MSG = b"mock-tar: metadata.log: Not found in mock-archive"
CANNOT_OPEN_MSG = (
    b"mock-tar: /mock/result.tar.xz: Cannot open: No such mock-file or mock-directory"
)


class TestCacheManager:
    def test_create(self, server_config, make_logger):
        """
        Create an empty CacheManager object and check the properties
        """
        cm = CacheManager(server_config, make_logger)
        assert cm is not None
        assert not cm.datasets  # No datasets expected
        assert not cm.tarballs  # No datasets expected
        assert not cm.controllers  # No controllers expected

        temp = re.compile(r"^(.*)/srv/pbench")
        match = temp.match(str(cm.archive_root))
        root = match.group(1)
        assert str(cm.archive_root) == root + "/srv/pbench/archive/fs-version-001"
        assert str(cm.cache_root) == root + "/srv/pbench/cache"

    def test_discover_empties(self, server_config, make_logger):
        """
        Full discovery with no controllers or datasets
        """
        cm = CacheManager(server_config, make_logger)
        cm.full_discovery()
        assert not cm.datasets  # No datasets expected
        assert not cm.tarballs  # No datasets expected
        assert not cm.controllers  # No controllers expected

    def test_empty_controller(self, server_config, make_logger):
        """
        Discover a "controller" directory with no datasets
        """
        cm = CacheManager(server_config, make_logger)
        test_controller = cm.archive_root / "TEST"
        test_controller.mkdir()
        cm.full_discovery()
        assert not cm.datasets  # No datasets expected
        assert not cm.tarballs  # No datasets expected
        assert list(cm.controllers.keys()) == ["TEST"]

    def test_clean_empties(self, server_config, make_logger):
        """
        Test that empty controller directories are removed
        """
        cm = CacheManager(server_config, make_logger)
        controllers = ["PLUGH", "XYZZY"]
        for c in controllers:
            (cm.archive_root / c).mkdir(parents=True)
        cm.full_discovery()
        ctrls = sorted(cm.controllers)
        assert ctrls == controllers

        for c in controllers:
            cm._clean_empties(c)
        assert not cm.controllers
        for c in controllers:
            assert not (cm.archive_root / c).exists()

    def test_metadata(
        self, monkeypatch, selinux_disabled, server_config, make_logger, tarball
    ):
        """Test behavior with metadata.log access errors."""

        def fake_metadata(_tar_path):
            return {"pbench": {"date": "2002-05-16T00:00:00"}}

        def fake_metadata_run(_tar_path):
            return {"pbench": {"date": "2002-05-16T00:00:00"}, "run": {}}

        def fake_metadata_controller(_tar_path):
            return {
                "pbench": {"date": "2002-05-16T00:00:00"},
                "run": {"controller": ""},
            }

        # fetching metadata from metadata.log file and key/value not
        # being there should result in a MetadataError
        source_tarball, source_md5, md5 = tarball
        cm = CacheManager(server_config, make_logger)

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: \"'run'\""
        with monkeypatch.context() as m:
            m.setattr(Tarball, "_get_metadata", fake_metadata)
            with pytest.raises(MetadataError) as exc:
                cm.create(source_tarball)
            assert str(exc.value) == expected_metaerror

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: \"'controller'\""
        with monkeypatch.context() as m:
            m.setattr(Tarball, "_get_metadata", fake_metadata_run)
            with pytest.raises(MetadataError) as exc:
                cm.create(source_tarball)
            assert str(exc.value) == expected_metaerror

        expected_metaerror = "A problem occurred processing metadata.log "
        expected_metaerror += f"from {source_tarball!s}: 'no controller value'"
        with monkeypatch.context() as m:
            m.setattr(Tarball, "_get_metadata", fake_metadata_controller)
            with pytest.raises(MetadataError) as exc:
                cm.create(source_tarball)
            assert str(exc.value) == expected_metaerror

    def test_with_metadata(
        self, monkeypatch, selinux_disabled, server_config, make_logger, tarball
    ):
        """Test behavior with metadata.log access errors."""
        source_tarball, source_md5, md5 = tarball
        cm = CacheManager(server_config, make_logger)

        with monkeypatch.context() as m:
            m.setattr(Tarball, "_get_metadata", fake_get_metadata)
            cm.create(source_tarball)
            tarball = cm.find_dataset(md5)
            assert tarball.metadata == fake_get_metadata(tarball.tarball_path)

    def test_create_bad(
        self, monkeypatch, selinux_disabled, server_config, make_logger, tarball
    ):
        """
        Test several varieties of dataset errors:

        1) Attempt to create a new dataset from an MD5 file
        2) Attempt to create a new dataset from a non-existent file
        3) Attempt to create a dataset that already exists
        """
        source_tarball, source_md5, md5 = tarball
        cm = CacheManager(server_config, make_logger)
        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)

        # Attempting to create a dataset from the md5 file should result in
        # a bad filename error
        with pytest.raises(DatasetBadName) as exc:
            cm.create(source_md5)
        assert exc.value.name == str(source_md5)

        cm.create(source_tarball)

        # The create call will remove the source files, so trying again should
        # result in an error.
        with pytest.raises(BadFilename) as exc:
            cm.create(source_md5)
        assert exc.value.path == str(source_md5)

        # Attempting to create the same dataset again (from the archive copy)
        # should fail with a duplicate dataset error.
        tarball = cm.find_dataset(md5)
        with pytest.raises(DuplicateTarball) as exc:
            cm.create(tarball.tarball_path)
        msg = "A dataset tarball named 'pbench-user-benchmark_some + config_2021.05.01T12.42.42' is already present"
        assert str(exc.value) == msg
        assert tarball.metadata == fake_get_metadata(tarball.tarball_path)
        assert exc.value.tarball == tarball.name

    def test_duplicate(
        self, monkeypatch, selinux_disabled, server_config, make_logger, tarball
    ):
        """
        Test behavior when we create a new dataset with a tarball file name
        and MD5 that already exists
        """

        source_tarball, source_md5, md5 = tarball
        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)
        cm = CacheManager(server_config, make_logger)

        # Create a tarball file in the expected destination directory: the
        # subsequent create should report a duplicate.
        controller = cm.archive_root / "ABC" / md5
        controller.mkdir(parents=True)
        (controller / source_tarball.name).write_text("Send in the clones")
        with pytest.raises(DuplicateTarball) as exc:
            cm.create(source_tarball)
        assert exc.value.tarball == Dataset.stem(source_tarball)

    @pytest.mark.parametrize(
        "allow,errno",
        (
            (".md5", errno.ENOSPC),
            (".md5", errno.EEXIST),
            (".md5", None),
            ("", errno.ENOSPC),
            ("", errno.EACCES),
            ("", None),
        ),
    )
    def test_move_fails(
        self,
        monkeypatch,
        selinux_disabled,
        server_config,
        make_logger,
        tarball,
        allow,
        errno,
    ):
        src: list[Path] = []
        dest: list[Path] = []
        real_move = shutil.move

        def mymove(source: Path, destination: Path, *args, **kwargs) -> Path:
            src.append(source)
            if destination.is_dir():
                d = destination / source.name
            else:
                d = destination
            dest.append(d)
            if source.suffix == allow:
                return real_move(source, destination, *args, **kwargs)
            if errno:
                e = OSError(errno, "something went badly")
            else:
                e = Exception("I broke")
            raise e

        ulink: list[Path] = []
        ok: list[bool] = []

        def unlink(self, missing_ok: bool = False):
            ulink.append(self)
            ok.append(missing_ok)

        source_tarball, source_md5, md5 = tarball
        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)
        cm = CacheManager(server_config, make_logger)
        monkeypatch.setattr("pbench.server.cache_manager.shutil.move", mymove)
        monkeypatch.setattr(Path, "unlink", unlink)
        with pytest.raises(Exception) as e:
            cm.create(source_tarball)
        if errno:
            assert isinstance(e.value, OSError), f"Wanted OSError, got {type(e.value)}"
            assert e.value.errno == errno
        else:
            assert str(e.value) == "I broke"
        assert src == [source_md5] + ([source_tarball] if allow else [])
        assert len(src) == len(dest) == len(ulink) == len(ok) == (2 if allow else 1)
        for i, s in enumerate(src):
            assert dest[i].name == s.name
            assert ulink[i].name == s.name
            assert dest[i] == ulink[i]
        assert all(ok), f"Cleanup unlinks don't ignore missing: {ok}, {ulink}"

    def test_tarball_subprocess_run_with_exception(self, monkeypatch):
        """Test to check the subprocess_run functionality of the Tarball when
        an Exception occurred"""
        my_command = "mycommand"

        def mock_run(args, **_kwargs):
            assert args[0] == my_command
            raise subprocess.TimeoutExpired(my_command, 43)

        with monkeypatch.context() as m:
            m.setattr(subprocess, "run", mock_run)
            command = f"{my_command} myarg"
            my_dir = "my_dir"

            with pytest.raises(TarballUnpackError) as exc:
                Tarball.subprocess_run(
                    command, my_dir, TarballUnpackError, Path(my_dir)
                )
            msg = f"An error occurred while unpacking {my_dir}: Command '{my_command}' timed out after 43 seconds"
            assert str(exc.value) == msg

    def test_tarball_subprocess_run_with_returncode(self, monkeypatch):
        """Test to check the subprocess_run functionality of the Tarball when
        returncode value is not zero"""
        my_command = "mycommand"

        def mock_run(args, **_kwargs):
            assert args[0] == my_command
            return subprocess.CompletedProcess(
                args, returncode=1, stdout=None, stderr="Some error unpacking tarball\n"
            )

        with monkeypatch.context() as m:
            m.setattr("subprocess.run", mock_run)
            command = f"{my_command} myarg"
            my_dir = Path("my_dir")

            with pytest.raises(TarballUnpackError) as exc:
                Tarball.subprocess_run(command, my_dir, TarballUnpackError, my_dir)

            msg = f"An error occurred while unpacking {my_dir.name}: {my_command} "
            msg += "exited with status 1:  'Some error unpacking tarball'"
            assert str(exc.value) == msg

    def test_tarball_subprocess_run_success(self, monkeypatch):
        """Test to check the successful run of subprocess_run functionality of the Tarball."""
        my_command = "mycommand"
        my_dir = Path("my_dir")
        run_called = False

        def mock_run(args, **kwargs):
            nonlocal run_called
            run_called = True

            assert args[0] == my_command
            assert kwargs["capture_output"]
            assert kwargs["text"]
            assert kwargs["cwd"] == my_dir
            assert kwargs["stdin"] == subprocess.DEVNULL
            return subprocess.CompletedProcess(
                args, returncode=0, stdout="Successfully Unpacked!", stderr=None
            )

        with monkeypatch.context() as m:
            m.setattr("subprocess.run", mock_run)
            command = f"{my_command} myarg"
            Tarball.subprocess_run(command, my_dir, TarballUnpackError, my_dir)
            assert run_called

    class MockController:
        def __init__(self, path: Path, cache: Path, logger: Logger):
            self.name = "ABC"
            self.path = path
            self.cache = cache
            self.logger = logger
            self.datasets = {}
            self.tarballs = {}

        @staticmethod
        def generate_test_result_tree(tmp_path: Path, dir_name: str) -> Path:
            """
            Directory Structure

            /tmp/
                <dir_name>/
                    subdir1/
                        subdir11/
                        subdir12/
                            f121_sym -> ../../subdir1/subdir15
                            f122_sym -> ./bad_subdir/nonexistent_file.txt
                        subdir13/
                            f131_sym -> /etc/passwd
                        subdir14/
                            subdir141/
                                f1411.txt
                                f1412_sym -> /tmp/<dir_name>/subdir1/f11.txt
                                f1413_sym -> ../subdir141
                                f1414_sym -> ./f1411.txt
                                f1415_sym -> ./f1412_sym
                                f1416_sym -> ../../subdir12/f122_sym
                        f11.txt
                        f12_sym -> ../../..
                    f1.json
                    metadata.log


            Generated cache map

            {
                'dir_name': {
                    'details': <cache_manager.FileInfo object>,
                    'children': {
                        'f1.json': {'details': <cache_manager.FileInfo object>},
                        'metadata.log': {'details': <cache_manager.FileInfo object>},
                        'subdir1': {
                            'details': <cache_manager.FileInfo object>,
                            'children': {
                                'f11.txt': {'details': <cache_manager.FileInfo object>},
                                'f12_sym': {'details': <cache_manager.FileInfo object>},
                                'subdir14': {
                                    'details': <cache_manager.FileInfo object>,
                                    'children': {
                                        'subdir141': {
                                            'details': <cache_manager.FileInfo object>,
                                            'children':{
                                                'f1411.txt': { 'details': <cache_manager.FileInfo object>},
                                                'f1412_sym': { 'details': <cache_manager.FileInfo object>},
                                                'f1413_sym': { 'details': <cache_manager.FileInfo object>},
                                                'f1414_sym': { 'details': <cache_manager.FileInfo object>},
                                                'f1415_sym': { 'details': <cache_manager.FileInfo object>},
                                                'f1416_sym': { 'details': <cache_manager.FileInfo object>},
                                            }}}},
                                'subdir13': {
                                    'details': <cache_manager.FileInfo object>,
                                    'children': {
                                        'f131_sym': {'details': <cache_manager.FileInfo object>}
                                    }},
                                'subdir12': {
                                    'details': <cache_manager.FileInfo object>,
                                    'children': {
                                        'f121_sym': {'details': <cache_manager.FileInfo object>},
                                        'f122_sym': {'details': <cache_manager.FileInfo object>}
                                    }},
                                'subdir11': {'details': <cache_manager.FileInfo object>, 'children': {}
                                }}}}}}
            """
            # create some directories and files inside the temp directory
            sub_dir = tmp_path / dir_name
            sub_dir.mkdir(parents=True, exist_ok=True)
            (sub_dir / "f1.json").touch()
            (sub_dir / "metadata.log").touch()
            for i in range(1, 4):
                (sub_dir / "subdir1" / f"subdir1{i}").mkdir(parents=True, exist_ok=True)
            (sub_dir / "subdir1" / "f11.txt").touch()
            (sub_dir / "subdir1" / "subdir14" / "subdir141").mkdir(
                parents=True, exist_ok=True
            )
            (sub_dir / "subdir1" / "subdir14" / "subdir141" / "f1411.txt").touch()
            sym_file = sub_dir / "subdir1" / "f12_sym"
            os.symlink(Path("../../.."), sym_file)
            sym_file = sub_dir / "subdir1" / "subdir12" / "f121_sym"
            os.symlink(Path("../..") / "subdir1" / "subdir15", sym_file)
            sym_file = sub_dir / "subdir1" / "subdir12" / "f122_sym"
            os.symlink(Path(".") / "bad_subdir" / "nonexistent_file.txt", sym_file)
            sym_file = sub_dir / "subdir1" / "subdir13" / "f131_sym"
            os.symlink(Path("/etc") / "passwd", sym_file)
            sym_file = sub_dir / "subdir1" / "subdir14" / "subdir141" / "f1412_sym"
            os.symlink(sub_dir / "subdir1" / "f11.txt", sym_file)
            sym_file = sub_dir / "subdir1" / "subdir14" / "subdir141" / "f1413_sym"
            os.symlink(Path("..") / "subdir141", sym_file)
            sym_file = sub_dir / "subdir1" / "subdir14" / "subdir141" / "f1414_sym"
            os.symlink(Path(".") / "f1411.txt", sym_file)
            sym_file = sub_dir / "subdir1" / "subdir14" / "subdir141" / "f1415_sym"
            os.symlink(Path(".") / "f1412_sym", sym_file)
            sym_file = sub_dir / "subdir1" / "subdir14" / "subdir141" / "f1416_sym"
            os.symlink(Path("../..") / "subdir12" / "f122_sym", sym_file)

            return sub_dir

    class MockTarball:
        def __init__(self, path: Path, resource_id: str, controller: Controller):
            self.name = Dataset.stem(path)
            self.tarball_path = path
            self.cache = controller.cache / "ABC"
            self.isolator = controller.path / resource_id
            self.unpacked = None
            self.controller = controller

    def test_unpack_tar_subprocess_exception(self, make_logger, monkeypatch):
        """Show that, when unpacking of the Tarball fails and raises
        an Exception it is handled successfully."""
        tar = Path("/mock/A.tar.xz")
        cache = Path("/mock/.cache")

        locks: list[tuple[str, str]] = []

        @contextmanager
        def open(s, m, buffering=-1):
            yield None

        def locker(fd, mode):
            nonlocal locks
            locks.append((fd, mode))

        @staticmethod
        def mock_run(command, _dir_path, exception, dir_p):
            verb = "tar"
            assert command.startswith(verb)
            raise exception(dir_p, subprocess.TimeoutExpired(verb, 43))

        with monkeypatch.context() as m:
            m.setattr(Path, "mkdir", lambda path, parents=False, exist_ok=False: None)
            m.setattr(Tarball, "subprocess_run", mock_run)
            m.setattr(Path, "open", open)
            m.setattr("pbench.server.cache_manager.fcntl.lockf", locker)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(
                tar, "ABC", Controller(Path("/mock/archive"), cache, make_logger)
            )
            with pytest.raises(TarballUnpackError) as exc:
                tb.cache_create()
            msg = f"An error occurred while unpacking {tar}: Command 'tar' timed out after 43 seconds"
            assert str(exc.value) == msg
            assert exc.type == TarballUnpackError

    def test_unpack_find_subprocess_exception(self, make_logger, monkeypatch):
        """Show that, when permission change of the Tarball fails and raises
        an Exception it is handled successfully."""
        tar = Path("/mock/A.tar.xz")
        cache = Path("/mock/.cache")
        rmtree_called = True

        locks: list[tuple[str, str]] = []

        @contextmanager
        def open(s, m, buffering=-1):
            yield None

        def locker(fd, mode):
            nonlocal locks
            locks.append((fd, mode))

        def mock_rmtree(path: Path, ignore_errors=False):
            nonlocal rmtree_called
            rmtree_called = True

            assert ignore_errors
            assert path == cache / "ABC"

        @staticmethod
        def mock_run(command, _dir_path, exception, dir_p):
            verb = "find"
            if command.startswith(verb):
                raise exception(dir_p, subprocess.TimeoutExpired(verb, 43))
            else:
                assert command.startswith("tar")

        with monkeypatch.context() as m:
            m.setattr(Path, "mkdir", lambda path, parents=False, exist_ok=False: None)
            m.setattr(Path, "open", open)
            m.setattr("pbench.server.cache_manager.fcntl.lockf", locker)
            m.setattr(Tarball, "subprocess_run", mock_run)
            m.setattr(shutil, "rmtree", mock_rmtree)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(
                tar, "ABC", Controller(Path("/mock/archive"), cache, make_logger)
            )

            with pytest.raises(TarballModeChangeError) as exc:
                tb.cache_create()
            msg = "An error occurred while changing file permissions of "
            msg += f"{cache / 'ABC'}: Command 'find' timed out after 43 seconds"
            assert str(exc.value) == msg
            assert exc.type == TarballModeChangeError
            assert rmtree_called

    def test_unpack_success(self, make_logger, monkeypatch):
        """Test to check the unpacking functionality of the CacheManager"""
        tar = Path("/mock/A.tar.xz")
        cache = Path("/mock/.cache")
        call = list()

        locks: list[tuple[str, str]] = []

        @contextmanager
        def open(s, m, buffering=-1):
            yield None

        def locker(fd, mode):
            nonlocal locks
            locks.append((fd, mode))

        def mock_run(args, **_kwargs):
            call.append(args[0])

            tar_target = "--file=" + str(tar)
            assert args[0] == "find" or args[0] == "tar" and tar_target in args
            return subprocess.CompletedProcess(
                args, returncode=0, stdout="Successfully Unpacked!", stderr=None
            )

        def mock_resolve(_path, _strict=False):
            """In this scenario, there are no symlinks,
            so resolve() should never be called."""
            raise AssertionError("Unexpected call to Path.resolve()")

        with monkeypatch.context() as m:
            m.setattr(Path, "mkdir", lambda path, parents=False, exist_ok=False: None)
            m.setattr(Path, "open", open)
            m.setattr("pbench.server.cache_manager.fcntl.lockf", locker)
            m.setattr("pbench.server.cache_manager.subprocess.run", mock_run)
            m.setattr(Path, "resolve", mock_resolve)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(
                tar, "ABC", Controller(Path("/mock/archive"), cache, make_logger)
            )
            tb.cache_create()
            assert call == ["tar", "find"]
            assert tb.unpacked == cache / "ABC" / tb.name

    def test_cache_map_success(self, make_logger, monkeypatch, tmp_path):
        """Test to build the cache map of the root directory"""
        tar = Path("/mock/dir_name.tar.xz")
        cache = Path("/mock/.cache")

        with monkeypatch.context() as m:
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(
                tar, "ABC", Controller(Path("/mock/archive"), cache, make_logger)
            )
            tar_dir = TestCacheManager.MockController.generate_test_result_tree(
                tmp_path, "dir_name"
            )
            tb.cache_map(tar_dir)

            sd1 = tb.cachemap["dir_name"]["children"]["subdir1"]
            assert sd1["details"].name == "subdir1"

            sd141 = sd1["children"]["subdir14"]["children"]["subdir141"]
            assert sd141["children"]["f1412_sym"]["details"].type == CacheType.SYMLINK

    @pytest.mark.parametrize(
        "file_path, expected_msg",
        [
            (
                "/dir_name/subdir1/f11.txt",
                "The path '/dir_name/subdir1/f11.txt' is an absolute path, "
                "we expect relative path to the root directory.",
            ),
            (
                "dir_name/subdir1/subdir11/../f11.txt",
                "directory 'dir_name/subdir1/subdir11/../f11.txt' doesn't have a '..' file/directory.",
            ),
            (
                "dir_name/subdir1/subdir14/subdir1",
                "directory 'dir_name/subdir1/subdir14/subdir1' doesn't have a 'subdir1' file/directory.",
            ),
            (
                "dir_name/ne_dir",
                "directory 'dir_name/ne_dir' doesn't have a 'ne_dir' file/directory.",
            ),
            (
                "dir_name/subdir1/ne_file",
                "directory 'dir_name/subdir1/ne_file' doesn't have a 'ne_file' file/directory.",
            ),
            (
                "dir_name/ne_dir/ne_file",
                "directory 'dir_name/ne_dir/ne_file' doesn't have a 'ne_dir' file/directory.",
            ),
            (
                "dir_name/subdir1/f11.txt/ne_subdir",
                "Found a file 'f11.txt' where a directory was expected in path 'dir_name/subdir1/f11.txt/ne_subdir'",
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1412_sym/ne_file",
                "Found a file 'f1412_sym' where a directory was expected "
                "in path 'dir_name/subdir1/subdir14/subdir141/f1412_sym/ne_file'",
            ),
        ],
    )
    def test_cache_map_bad_dir_path(
        self, make_logger, monkeypatch, tmp_path, file_path, expected_msg
    ):
        """Test to check bad directory or file path"""
        tar = Path("/mock/dir_name.tar.xz")
        cache = Path("/mock/.cache")

        with monkeypatch.context() as m:
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(
                tar, "ABC", Controller(Path("/mock/archive"), cache, make_logger)
            )
            tar_dir = TestCacheManager.MockController.generate_test_result_tree(
                tmp_path, "dir_name"
            )
            tb.cache_map(tar_dir)
            with pytest.raises(BadDirpath) as exc:
                tb.get_info(Path(file_path))
            assert str(exc.value) == expected_msg

    @pytest.mark.parametrize(
        "file_path, location, name, resolve_path, resolve_type, size, file_type",
        [
            ("dir_name", "dir_name", "dir_name", None, None, None, CacheType.DIRECTORY),
            (
                "dir_name/f1.json",
                "dir_name/f1.json",
                "f1.json",
                None,
                None,
                0,
                CacheType.FILE,
            ),
            (
                "dir_name/subdir1",
                "dir_name/subdir1",
                "subdir1",
                None,
                None,
                None,
                CacheType.DIRECTORY,
            ),
            (
                "dir_name/subdir1/./f11.txt",
                "dir_name/subdir1/f11.txt",
                "f11.txt",
                None,
                None,
                0,
                CacheType.FILE,
            ),
            (
                "dir_name/subdir1//f11.txt",
                "dir_name/subdir1/f11.txt",
                "f11.txt",
                None,
                None,
                0,
                CacheType.FILE,
            ),
            (
                "dir_name/subdir1/f11.txt",
                "dir_name/subdir1/f11.txt",
                "f11.txt",
                None,
                None,
                0,
                CacheType.FILE,
            ),
            (
                "dir_name/subdir1/f12_sym",
                "dir_name/subdir1/f12_sym",
                "f12_sym",
                Path("../../.."),
                CacheType.OTHER,
                None,
                CacheType.SYMLINK,
            ),
            (
                "dir_name/subdir1/subdir12/f121_sym",
                "dir_name/subdir1/subdir12/f121_sym",
                "f121_sym",
                Path("../../subdir1/subdir15"),
                CacheType.OTHER,
                None,
                CacheType.SYMLINK,
            ),
            (
                "dir_name/subdir1/subdir12/f122_sym",
                "dir_name/subdir1/subdir12/f122_sym",
                "f122_sym",
                Path("bad_subdir/nonexistent_file.txt"),
                CacheType.OTHER,
                None,
                CacheType.SYMLINK,
            ),
            (
                "dir_name/subdir1/subdir13/f131_sym",
                "dir_name/subdir1/subdir13/f131_sym",
                "f131_sym",
                Path("/etc/passwd"),
                CacheType.OTHER,
                None,
                CacheType.SYMLINK,
            ),
            (
                "dir_name/subdir1/subdir14",
                "dir_name/subdir1/subdir14",
                "subdir14",
                None,
                None,
                None,
                CacheType.DIRECTORY,
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1411.txt",
                "dir_name/subdir1/subdir14/subdir141/f1411.txt",
                "f1411.txt",
                None,
                None,
                0,
                CacheType.FILE,
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1412_sym",
                "dir_name/subdir1/subdir14/subdir141/f1412_sym",
                "f1412_sym",
                Path("/mock_absolute_path/subdir1/f11.txt"),
                CacheType.OTHER,
                None,
                CacheType.SYMLINK,
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1413_sym",
                "dir_name/subdir1/subdir14/subdir141/f1413_sym",
                "f1413_sym",
                Path("dir_name/subdir1/subdir14/subdir141"),
                CacheType.DIRECTORY,
                None,
                CacheType.SYMLINK,
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1414_sym",
                "dir_name/subdir1/subdir14/subdir141/f1414_sym",
                "f1414_sym",
                Path("dir_name/subdir1/subdir14/subdir141/f1411.txt"),
                CacheType.FILE,
                None,
                CacheType.SYMLINK,
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1415_sym",
                "dir_name/subdir1/subdir14/subdir141/f1415_sym",
                "f1415_sym",
                Path("dir_name/subdir1/f11.txt"),
                CacheType.FILE,
                None,
                CacheType.SYMLINK,
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1416_sym",
                "dir_name/subdir1/subdir14/subdir141/f1416_sym",
                "f1416_sym",
                Path("../../subdir12/f122_sym"),
                CacheType.OTHER,
                None,
                CacheType.SYMLINK,
            ),
        ],
    )
    def test_cache_map_traverse_cmap(
        self,
        make_logger,
        monkeypatch,
        tmp_path,
        file_path,
        location,
        name,
        resolve_path,
        resolve_type,
        size,
        file_type,
    ):
        """Test to check the sanity of details of the cachemap"""
        tar = Path("/mock/dir_name.tar.xz")
        cache = Path("/mock/.cache")

        with monkeypatch.context() as m:
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(
                tar, "ABC", Controller(Path("/mock/archive"), cache, make_logger)
            )
            tar_dir = TestCacheManager.MockController.generate_test_result_tree(
                tmp_path, "dir_name"
            )
            tb.cache_map(tar_dir)

            # Since the result tree is dynamically generated by the test at runtime,
            # the parametrization for resolve_path cannot provide the correct value
            # if the path is an absolute reference; therefore, we detect those cases
            # here and modify the value.
            abs_pref = "/mock_absolute_path/"
            if str(resolve_path).startswith(abs_pref):
                resolve_path = tar_dir / str(resolve_path).removeprefix(abs_pref)

            # test traverse with random path
            c_map = Tarball.traverse_cmap(Path(file_path), tb.cachemap)
            assert c_map["details"].location == Path(location)
            assert c_map["details"].name == name
            assert c_map["details"].resolve_path == resolve_path
            assert c_map["details"].resolve_type == resolve_type
            assert c_map["details"].size == size
            assert c_map["details"].type == file_type

    @pytest.mark.parametrize(
        "file_path, expected_msg",
        [
            (
                "dir_name/subdir1/f11.txt",
                {
                    "location": Path("dir_name/subdir1/f11.txt"),
                    "name": "f11.txt",
                    "resolve_path": None,
                    "resolve_type": None,
                    "size": 0,
                    "type": CacheType.FILE,
                },
            ),
            (
                "dir_name/subdir1",
                {
                    "directories": ["subdir11", "subdir12", "subdir13", "subdir14"],
                    "files": ["f11.txt"],
                    "location": Path("dir_name/subdir1"),
                    "name": "subdir1",
                    "resolve_path": None,
                    "resolve_type": None,
                    "size": None,
                    "type": CacheType.DIRECTORY,
                },
            ),
            (
                "dir_name/subdir1/subdir11",
                {
                    "directories": [],
                    "files": [],
                    "location": Path("dir_name/subdir1/subdir11"),
                    "name": "subdir11",
                    "resolve_path": None,
                    "resolve_type": None,
                    "size": None,
                    "type": CacheType.DIRECTORY,
                },
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1413_sym",
                {
                    "location": Path("dir_name/subdir1/subdir14/subdir141/f1413_sym"),
                    "name": "f1413_sym",
                    "resolve_path": Path("dir_name/subdir1/subdir14/subdir141"),
                    "resolve_type": CacheType.DIRECTORY,
                    "size": None,
                    "type": CacheType.SYMLINK,
                },
            ),
        ],
    )
    def test_cache_map_get_info_cmap(
        self, make_logger, monkeypatch, tmp_path, file_path, expected_msg
    ):
        """Test to check if the info returned by the cachemap is correct"""
        tar = Path("/mock/dir_name.tar.xz")
        cache = Path("/mock/.cache")

        with monkeypatch.context() as m:
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(
                tar, "ABC", Controller(Path("/mock/archive"), cache, make_logger)
            )
            tar_dir = TestCacheManager.MockController.generate_test_result_tree(
                tmp_path, "dir_name"
            )
            tb.cache_map(tar_dir)

            # test get_info with random path
            file_info = tb.get_info(Path(file_path))
            assert file_info == expected_msg

    @pytest.mark.parametrize(
        "file_path,file_pattern,exp_stream",
        [
            ("", "dir_name.tar.xz", io.BytesIO(b"tarball_as_a_byte_stream")),
            (None, "dir_name.tar.xz", io.BytesIO(b"tarball_as_a_byte_stream")),
            ("f1.json", "f1.json", io.BytesIO(b"file_as_a_byte_stream")),
            ("subdir1/f12_sym", None, CacheExtractBadPath(Path("a"), "b")),
        ],
    )
    def test_get_inventory(
        self, make_logger, monkeypatch, tmp_path, file_path, file_pattern, exp_stream
    ):
        """Test to extract file contents/stream from a file"""
        archive = tmp_path / "mock/archive"
        tar = archive / "ABC/dir_name.tar.xz"
        cache = tmp_path / "mock/.cache"

        locks: list[tuple[str, str]] = []

        def locker(fd, mode):
            nonlocal locks
            locks.append((fd, mode))

        with monkeypatch.context() as m:
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            real_open = Path.open
            m.setattr(
                Path,
                "open",
                lambda s, m="rb", buffering=-1: exp_stream
                if file_pattern and file_pattern in str(s)
                else real_open(s, m, buffering),
            )
            m.setattr("pbench.server.cache_manager.fcntl.lockf", locker)
            tb = Tarball(
                tar, "ABC", Controller(archive, cache, make_logger)
            )
            tb.unpacked = cache / "ABC/dir_name"
            tar_dir = TestCacheManager.MockController.generate_test_result_tree(
                cache / "ABC", "dir_name"
            )
            tb.cache_map(tar_dir)
            try:
                file_info = tb.get_inventory(file_path)
            except Exception as e:
                assert isinstance(e, type(exp_stream)), e
            else:
                assert not isinstance(exp_stream, Exception)
                assert file_info["type"] is CacheType.FILE
                stream: Inventory = file_info["stream"]
                assert stream.stream == exp_stream
                stream.close()
                if not file_path:
                    assert len(locks) == 0
                else:
                    assert list(i[1] for i in locks) == [
                        fcntl.LOCK_EX,
                        fcntl.LOCK_UN,
                        fcntl.LOCK_SH,
                        fcntl.LOCK_UN,
                    ]

    def test_cm_inventory(self, monkeypatch, server_config, make_logger):
        """Verify the happy path of the high level get_inventory"""
        dataset_id = None

        class MockTarball:
            def get_inventory(self, target: str) -> JSONOBJECT:
                return {
                    "name": target if self else None,  # Quiet the linter
                    "type": CacheType.FILE,
                    "stream": Inventory(io.BytesIO(b"success")),
                }

        def mock_find_dataset(_self, dataset: str) -> MockTarball:
            nonlocal dataset_id
            dataset_id = dataset

            return MockTarball()

        with monkeypatch.context() as m:
            m.setattr(CacheManager, "find_dataset", mock_find_dataset)
            cm = CacheManager(server_config, make_logger)
            inventory = cm.get_inventory("dataset", "target")
            assert dataset_id == "dataset"
            assert inventory["name"] == "target"
            assert inventory["stream"].read() == b"success"

    @pytest.mark.parametrize(
        (
            "tar_path",
            "popen_fail",
            "wait_cnt",
            "peek_return",
            "poll_return",
            "proc_return",
            "stderr_contents",
        ),
        (
            (None, False, 0, b"", None, 2, b""),  # No tar executable
            ("/usr/bin/tar", True, 0, b"", None, 2, b""),  # Popen failure
            # Success, output in peek
            ("/usr/bin/tar", False, 0, b"[test]", None, 0, b""),
            ("/usr/bin/tar", False, 0, b"", 0, 0, b""),  # Success, poll() show success
            # Loop/sleep twice, then success
            ("/usr/bin/tar", False, 2, b"[test]", None, 0, b""),
            # Member path failure
            ("/usr/bin/tar", False, 0, b"", 1, 1, MEMBER_NOT_FOUND_MSG),
            # Archive access failure
            ("/usr/bin/tar", False, 0, b"", 1, 1, CANNOT_OPEN_MSG),
            # Unexpected failure
            ("/usr/bin/tar", False, 0, b"", 1, 1, b"mock-tar: bolt out of the blue!"),
            # Hang, never returning output nor an exit code
            ("/usr/bin/tar", False, 0, b"", None, None, b""),
        ),
    )
    def test_tarfile_extract(
        self,
        monkeypatch,
        tmp_path,
        tar_path: str,
        popen_fail: bool,
        wait_cnt: int,
        peek_return: Optional[bytes],
        poll_return: Optional[int],
        proc_return: int,
        stderr_contents: Optional[bytes],
    ):
        """Test to check Tarball.extract behaviors"""
        tar = Path("/mock/result.tar.xz")
        path = "metadata.log"
        stdout_contents = b"[test]\nfoo=bar\n"

        class MockBufferedReader(io.BufferedReader):
            def __init__(self, contents: bytes):
                # No effect, other than to quiet the linter
                None if True else super().__init__(io.RawIOBase())
                self.contents = contents
                self.loop_count = wait_cnt

            def close(self) -> None:
                raise AssertionError(
                    "This test doesn't expect the stream to be closed."
                )

            def peek(self, size=0) -> bytes:
                if self.loop_count > 0:
                    self.loop_count -= 1
                    return b""
                return peek_return

            def read(self, _size: int = -1) -> bytes:
                return self.contents

        class MockPopen(subprocess.Popen):
            def __init__(self, *_args, **_kwargs):
                # No effect, other than to quiet the linter
                None if True else super().__init__([])
                if popen_fail:
                    raise ValueError(
                        "MockPopen pretending it was called with invalid arguments"
                    )
                self.stdout = MockBufferedReader(stdout_contents)
                self.stderr = MockBufferedReader(stderr_contents)
                self.returncode = None
                self.loop_count = wait_cnt

            def poll(self) -> Optional[int]:
                if self.loop_count > 0:
                    self.loop_count -= 1
                    return None
                self.returncode = poll_return
                return poll_return

            def kill(self) -> None:
                pass

        def mock_shutil_which(
            cmd: str, _mode: int = os.F_OK | os.X_OK, _path: Optional[str] = None
        ):
            assert cmd == "tar"
            return tar_path

        with monkeypatch.context() as m:
            m.setattr(shutil, "which", mock_shutil_which)
            m.setattr(subprocess, "Popen", MockPopen)
            m.setattr(Inventory, "close", MockBufferedReader.close)
            m.setattr(Tarball, "TAR_EXEC_TIMEOUT", 0.1)

            try:
                got = Tarball.extract(tar, path)
            except CacheExtractBadPath as exc:
                assert tar_path
                assert not popen_fail
                assert stderr_contents == MEMBER_NOT_FOUND_MSG
                assert str(exc) == f"Unable to extract {path} from {tar.name}"
            except subprocess.TimeoutExpired as exc:
                assert tar_path
                assert not popen_fail
                assert (
                    not peek_return and not poll_return
                ), f"Unexpected test timeout: {exc}"
            except TarballUnpackError as exc:
                if tar_path is None:
                    msg = "External 'tar' executable not found"
                else:
                    assert not popen_fail
                    msg = f"Unexpected error from {tar_path}: {stderr_contents.decode()!r}"
                assert stderr_contents != MEMBER_NOT_FOUND_MSG
                assert str(exc) == f"An error occurred while unpacking {tar}: {msg}"
            except ValueError:
                assert tar_path
                assert popen_fail
            else:
                assert tar_path
                assert not popen_fail
                assert peek_return or poll_return is not None
                assert isinstance(got, Inventory)
                assert got.read() == stdout_contents

    @pytest.mark.parametrize(
        "tarball,stream", (("hasmetalog.tar.xz", True), ("nometalog.tar.xz", False))
    )
    def test_get_metadata(self, monkeypatch, tarball, stream):
        """Verify access and processing of `metadata.log`"""

        def fake_extract(t: Path, f: Path):
            if str(t) == tarball and str(f) == f"{Dataset.stem(t)}/metadata.log":
                if stream:
                    return Inventory(io.BytesIO(b"[test]\nfoo = bar\n"))
                raise CacheExtractBadPath(t, f)
            raise Exception(f"Unexpected mock exception with stream:{stream}: {t}, {f}")

        with monkeypatch.context() as m:
            m.setattr(Tarball, "extract", staticmethod(fake_extract))
            metadata = Tarball._get_metadata(Path(tarball))

        if stream:
            assert metadata == {"test": {"foo": "bar"}}
        else:
            assert metadata is None

    def test_inventory_without_subprocess(self):
        """Test the Inventory class when used without a subprocess

        This tests the Inventory class functions other than close(), which are
        unaffected by whether a subprocess is driving the stream, and it also
        tests the behavior of close() when there is no subprocess.
        """
        calls = []
        my_buffer = bytes()

        class MockBufferedReader(io.BufferedReader):
            def __init__(self):
                # No effect, other than to quiet the linter
                None if True else super().__init__(io.RawIOBase())

            def close(self) -> None:
                calls.append("close")

            def getbuffer(self):
                calls.append("getbuffer") if self else None  # Quiet the linter
                return my_buffer

            def read(self, _size: int = -1) -> bytes:
                calls.append("read")
                return b"read"

            def readable(self) -> bool:
                calls.append("readable")
                return True

            def readline(self, _size: int = -1) -> bytes:
                """Return a non-empty byte-string on the first call; return an
                empty string on subsequent calls."""
                calls.append("readline")
                return b"readline" if len(calls) < 2 else b""

            def seek(self, offset: int, _whence: int = io.SEEK_SET) -> int:
                calls.append("seek")
                return offset

        # Invoke the CUT
        stream = Inventory(MockBufferedReader())

        assert stream.lock is None

        # Test Inventory.getbuffer()
        calls.clear()
        assert stream.getbuffer() is my_buffer and calls == ["getbuffer"]

        # Test Inventory.read()
        calls.clear()
        assert stream.read() == b"read" and calls == ["read"]

        # Test Inventory.readable()
        calls.clear()
        assert stream.readable() and calls == ["readable"]

        # Test Inventory.seek()
        calls.clear()
        assert stream.seek(12345) == 12345 and calls == ["seek"]

        # Test Inventory.__iter__() and Inventory.__next__()
        calls.clear()
        contents = [b for b in stream]
        assert contents == [b"readline"] and calls == ["readline", "readline"]

        # Test Inventory.__repr__()
        assert str(stream) == "<Stream <MockBufferedReader> from None>"

        # Test Inventory.close()
        calls.clear()
        stream.close()
        assert calls == ["close"]

    @pytest.mark.parametrize(
        ("poll_val", "stdout_size", "stderr_size", "wait_timeout", "exp_calls"),
        (
            # The subprocess completed before the close() call
            (0, 0, None, None, ["poll", "close"]),
            # The subprocess is still running when close() is called, the wait
            # does not time out, stdout is empty and there is no stderr.
            (None, 0, None, False, ["poll", "kill", "stdout", "wait", "close"]),
            # The subprocess is still running when close() is called, the wait
            # does not time out, stderr is empty and there is no stdout.
            (None, None, 0, False, ["poll", "kill", "stderr", "wait", "close"]),
            # The subprocess is still running when close() is called, the wait
            # does not time out, both stdout and stderr are present and empty.
            (None, 0, 0, False, ["poll", "kill", "stdout", "stderr", "wait", "close"]),
            # The subprocess is still running when close() is called, the wait
            # does not time out, stdout and stderr each require one read to
            # drain them (and a second to see that they are empty).
            (
                None,
                2000,
                2000,
                False,
                [
                    "poll",
                    "kill",
                    "stdout",
                    "stdout",
                    "stderr",
                    "stderr",
                    "wait",
                    "close",
                ],
            ),
            # The subprocess is still running when close() is called, the wait
            # does not time out, stdout and stderr each require two reads to
            # drain them (and a third to see that they are empty).
            (
                None,
                6000,
                6000,
                False,
                [
                    "poll",
                    "kill",
                    "stdout",
                    "stdout",
                    "stdout",
                    "stderr",
                    "stderr",
                    "stderr",
                    "wait",
                    "close",
                ],
            ),
            # The subprocess is still running when close() is called, the wait
            # does not time out, stdout and stderr each require three reads to
            # drain them (and a fourth to see that they are empty).
            (
                None,
                9000,
                9000,
                False,
                [
                    "poll",
                    "kill",
                    "stdout",
                    "stdout",
                    "stdout",
                    "stdout",
                    "stderr",
                    "stderr",
                    "stderr",
                    "stderr",
                    "wait",
                    "close",
                ],
            ),
            # The subprocess is still running when close() is called, stdout is
            # empty, there is no stderr, and the wait times out.
            (None, 0, None, True, ["poll", "kill", "stdout", "wait"]),
        ),
    )
    def test_inventory(
        self, poll_val, stdout_size, stderr_size, wait_timeout, exp_calls
    ):
        """Test the Inventory class when used with a subprocess

        This test focuses on the behavior of the close() function, since the
        behavior of the other functions are checked in the previous test.
        """
        my_calls = []

        class MockPopen(subprocess.Popen):
            def __init__(
                self,
                stdout: Optional[io.BufferedReader],
                stderr: Optional[io.BufferedReader],
            ):
                # No effect, other than to quiet the linter.
                None if True else super().__init__([])
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = None

            def kill(self):
                my_calls.append("kill")

            def poll(self) -> Optional[int]:
                my_calls.append("poll")
                assert (
                    self.returncode is None
                ), "returncode is unexpectedly set...test bug?"
                self.returncode = poll_val
                return self.returncode

            def wait(self, timeout: Optional[float] = None) -> Optional[int]:
                my_calls.append("wait")
                assert (
                    self.returncode is None
                ), "returncode is unexpectedly set...test bug?"
                if wait_timeout:
                    raise subprocess.TimeoutExpired(
                        cmd="mock_subprocess",
                        timeout=timeout,
                        output=b"I'm dead!",
                        stderr=b"No, really, I'm dead!",
                    )
                self.returncode = 0
                return self.returncode

            def __repr__(self):
                return self.__class__.__name__

        class MockBufferedReader(io.BufferedReader):
            def __init__(self, size: int, name: str):
                # No effect, other than to quiet the linter
                None if True else super().__init__(io.RawIOBase())
                self.size = size
                self.stream_name = name

            def close(self) -> None:
                my_calls.append("close")
                pass

            def read(self, size: int = -1) -> bytes:
                my_calls.append(self.stream_name)
                if self.size <= 0:
                    return b""
                if size < 0 or size >= self.size:
                    self.size = 0
                else:
                    self.size -= size
                return b"read"

        my_stdout = (
            None if stdout_size is None else MockBufferedReader(stdout_size, "stdout")
        )
        my_stderr = (
            None if stderr_size is None else MockBufferedReader(stderr_size, "stderr")
        )
        my_stream = my_stdout if my_stdout is not None else my_stderr
        assert my_stream, "Test bug:  we need at least one of stdout and stderr"

        # Invoke the CUT
        stream = Inventory(my_stream, subproc=MockPopen(my_stdout, my_stderr))

        # Test Inventory.__repr__()
        assert str(stream) == "<Stream <MockBufferedReader> from MockPopen>"

        try:
            stream.close()
        except subprocess.TimeoutExpired:
            assert wait_timeout, "wait() timed out unexpectedly"
        else:
            assert not wait_timeout, "wait() failed to time out as expected"

        assert stream.lock is None
        assert my_calls == exp_calls

    def test_find(
        self, selinux_enabled, server_config, make_logger, tarball, monkeypatch
    ):
        """
        Create a dataset, check the cache manager state, and test that we can find it
        through the various supported methods.
        """

        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)
        source_tarball, source_md5, md5 = tarball
        dataset_name = Dataset.stem(source_tarball)
        cm = CacheManager(server_config, make_logger)
        cm.create(source_tarball)

        # The original files should have been removed
        assert not source_tarball.exists()
        assert not source_md5.exists()

        tarball = cm.find_dataset(md5)
        assert tarball
        assert tarball.name == dataset_name
        assert tarball.resource_id == md5

        # Test __getitem__
        assert tarball == cm[md5]
        with pytest.raises(TarballNotFound) as exc:
            _ = cm["foobar"]
        assert str(exc.value) == "The dataset tarball named 'foobar' is not found"

        # Test __contains__
        assert md5 in cm
        assert "foobar" not in cm

        # There should be nothing else in the cache manager
        controller = tarball.controller

        assert cm.controllers == {"ABC": controller}
        assert cm.datasets == {md5: tarball}

        # It hasn't been unpacked
        assert tarball.unpacked is None
        assert tarball.cache == controller.cache / md5

        # Try to find a dataset that doesn't exist
        with pytest.raises(TarballNotFound) as exc:
            cm.find_dataset("foobar")
        assert str(exc.value) == "The dataset tarball named 'foobar' is not found"
        assert exc.value.tarball == "foobar"

        # Unpack the dataset, creating INCOMING and RESULTS links
        cm.unpack(md5)
        assert tarball.cache == controller.cache / md5
        assert tarball.unpacked == controller.cache / md5 / tarball.name

        # We should be able to find the tarball even in a new cache manager
        # that hasn't been fully discovered.
        new = CacheManager(server_config, make_logger)
        assert md5 not in new

        tarball = new.find_dataset(md5)
        assert tarball
        assert tarball.name == dataset_name

        # We should have discovered the INCOMING and RESULTS data automagically
        assert tarball.unpacked == controller.cache / md5 / tarball.name

        # We should have just one controller and one tarball
        assert tarball.resource_id == md5
        assert list(new.controllers) == ["ABC"]
        assert list(new.datasets) == [md5]
        assert list(new.tarballs) == [dataset_name]

    def test_lifecycle(
        self, selinux_enabled, server_config, make_logger, tarball, monkeypatch
    ):
        """
        Create a dataset, unpack it, remove the unpacked version, and finally
        delete it.
        """

        source_tarball, source_md5, md5 = tarball
        cm = CacheManager(server_config, make_logger)
        archive = cm.archive_root / "ABC"
        cache = cm.cache_root / md5
        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)

        # None of the controller directories should exist yet
        assert not archive.exists()
        assert not cache.exists()

        # Create a dataset in the cache manager from our source tarball
        cm.create(source_tarball)

        # Expect the archive directory was created, but we haven't unpacked so
        # incoming and results should not exist.
        assert archive.exists()
        assert not cache.exists()

        # The original files should have been removed
        assert not source_tarball.exists()
        assert not source_md5.exists()

        tarfile = archive / md5 / source_tarball.name
        md5file = archive / md5 / source_md5.name
        assert tarfile.exists()
        assert md5file.exists()

        assert md5 == md5file.read_text().split()[0]
        md5_hash = hashlib.md5()
        md5_hash.update(tarfile.read_bytes())
        assert md5 == md5_hash.hexdigest()

        assert list(cm.controllers.keys()) == ["ABC"]
        dataset_name = source_tarball.name[:-7]
        assert list(cm.tarballs) == [dataset_name]
        assert list(cm.datasets) == [md5]

        # Now "unpack" the tarball and check that the incoming directory and
        # results link are set up.
        cm.unpack(md5)
        assert cache == cm[md5].cache
        assert cache.is_dir()
        assert (cache / dataset_name).is_dir()

        assert cm.datasets[md5].unpacked == cache / dataset_name

        # Re-discover, with all the files in place, and compare
        newcm = CacheManager(server_config, make_logger)
        newcm.full_discovery()

        assert newcm.archive_root == cm.archive_root
        assert newcm.cache_root == cm.cache_root
        assert sorted(newcm.controllers) == sorted(cm.controllers)
        assert sorted(newcm.datasets) == sorted(cm.datasets)
        assert sorted(newcm.tarballs) == sorted(cm.tarballs)
        for controller in cm.controllers.values():
            other = newcm.controllers[controller.name]
            assert controller.name == other.name
            assert controller.path == other.path
            assert controller.cache == controller.cache
            assert sorted(controller.datasets) == sorted(other.datasets)
            assert sorted(controller.tarballs) == sorted(other.tarballs)
        for tarball in cm.datasets.values():
            other = newcm.datasets[tarball.resource_id]
            assert tarball.name == other.name
            assert tarball.resource_id == other.resource_id
            assert tarball.controller_name == other.controller_name
            assert tarball.tarball_path == other.tarball_path
            assert tarball.md5_path == other.md5_path
            assert tarball.cache == other.cache
            assert tarball.unpacked == other.unpacked

        # Remove the unpacked tarball, and confirm that the directory and link
        # are removed.
        cm.cache_reclaim(md5)
        assert not cache.exists()

        # Now that we have all that setup, delete the dataset
        cm.delete(md5)
        assert not archive.exists()
        assert not cm.controllers
        assert not cm.datasets

    def test_compatibility(
        self, selinux_enabled, server_config, make_logger, tarball, monkeypatch
    ):
        """Test compatibility with both new "isolated" and old tarballs

        Make sure we can discover and manage (unpack and delete) both new
        tarballs with an MD5 isolation directory and pre-existing tarballs
        directly in the controller directory.
        """

        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)
        source_tarball, source_md5, md5 = tarball
        cm = CacheManager(server_config, make_logger)

        archive = cm.archive_root / "ABC"

        # Manually create an unisolated "pre-existing" copy of the tarball and
        # MD5 file in the controller directory.

        _, id = make_tarball(archive / source_tarball.name, "2023-09-18")
        assert id != md5
        cm.create(source_tarball)

        # Rediscover the cache, which should find both tarballs
        cm1 = CacheManager(server_config, make_logger).full_discovery()
        t1 = cm1[md5]
        t2 = cm1[id]
        assert t1.name == t2.name == Dataset.stem(source_tarball)

        t1.unpack()
        t2.unpack()

        assert t1.unpacked != t2.unpacked
        assert (t1.unpacked / "metadata.log").is_file()
        assert (t2.unpacked / "metadata.log").is_file()

        tar1 = t1.tarball_path
        tar2 = t2.tarball_path

        assert tar1 == tar2.parent / t1.resource_id / tar1.name

        t1.delete()
        t2.delete()

        # Check that the tarballs, and the tar1 isolation directory,
        # were removed.
        assert not tar1.exists()
        assert not tar2.exists()
        assert not tar1.parent.exists()
