import hashlib
from logging import Logger
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

import pytest

from pbench.server.cache_manager import (
    BadDirpath,
    BadFilename,
    CacheManager,
    CacheType,
    Controller,
    DuplicateTarball,
    MetadataError,
    Tarball,
    TarballModeChangeError,
    TarballNotFound,
    TarballUnpackError,
)
from pbench.server.database.models.datasets import Dataset, DatasetBadName


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


def fake_get_metadata(tb_path):
    return {"pbench": {"date": "2002-05-16T00:00:00"}, "run": {"controller": "ABC"}}


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

        def fake_extract_file(self, path):
            raise KeyError(f"filename {path} not found")

        def fake_tarfile_open(self, path):
            raise tarfile.TarError("Invalid Tarfile")

        def fake_metadata(tar_path):
            return {"pbench": {"date": "2002-05-16T00:00:00"}}

        def fake_metadata_run(tar_path):
            return {"pbench": {"date": "2002-05-16T00:00:00"}, "run": {}}

        def fake_metadata_controller(tar_path):
            return {
                "pbench": {"date": "2002-05-16T00:00:00"},
                "run": {"controller": ""},
            }

        # fetching metadata from metadata.log file and key/value not
        # being there should result in a MetadataError
        source_tarball, source_md5, md5 = tarball
        cm = CacheManager(server_config, make_logger)

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: 'Invalid Tarfile'"
        with monkeypatch.context() as m:
            m.setattr(tarfile, "open", fake_tarfile_open)
            with pytest.raises(MetadataError) as exc:
                cm.create(source_tarball)
            assert str(exc.value) == expected_metaerror

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

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: 'no controller value'"
        with monkeypatch.context() as m:
            m.setattr(Tarball, "_get_metadata", fake_metadata_controller)
            with pytest.raises(MetadataError) as exc:
                cm.create(source_tarball)
            assert str(exc.value) == expected_metaerror

        with monkeypatch.context() as m:
            m.setattr(tarfile.TarFile, "extractfile", fake_extract_file)
            cm.create(source_tarball)
            assert cm[md5].metadata is None

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

        # The create will remove the source files, so trying again should
        # result in an error.
        with pytest.raises(BadFilename) as exc:
            cm.create(source_md5)
        assert exc.value.path == str(source_md5)

        # Attempting to create the same dataset again (from the archive copy)
        # should fail with a duplicate dataset error.
        tarball = cm.find_dataset(md5)
        with pytest.raises(DuplicateTarball) as exc:
            cm.create(tarball.tarball_path)
        assert (
            str(exc.value)
            == "A dataset tarball named 'pbench-user-benchmark_some + config_2021.05.01T12.42.42' is already present in the cache manager"
        )
        assert tarball.metadata == fake_get_metadata(tarball.tarball_path)
        assert exc.value.tarball == tarball.name

    def test_duplicate(
        self, monkeypatch, selinux_disabled, server_config, make_logger, tarball
    ):
        """
        Test behavior when we try to create a new dataset but the tarball file
        name already exists
        """

        source_tarball, source_md5, md5 = tarball
        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)
        cm = CacheManager(server_config, make_logger)

        # Create a tarball file in the expected destination directory
        controller = cm.archive_root / "ABC"
        controller.mkdir()
        (controller / source_tarball.name).write_text("Send in the clones")

        # Attempting to create a dataset from the md5 file should result in
        # a duplicate dataset error
        with pytest.raises(DuplicateTarball) as exc:
            cm.create(source_tarball)
        assert exc.value.tarball == Dataset.stem(source_tarball)

    def test_tarball_subprocess_run_with_exception(self, monkeypatch):
        """Test to check the subprocess_run functionality of the Tarball when
        an Exception occured"""
        my_command = "mycommand"

        def mock_run(args, **kwargs):
            assert args[0] == my_command
            raise subprocess.TimeoutExpired(my_command, 43)

        with monkeypatch.context() as m:
            m.setattr(subprocess, "run", mock_run)
            command = f"{my_command} myarg"
            my_dir = "my_dir"

            with pytest.raises(TarballUnpackError) as exc:
                Tarball.subprocess_run(command, my_dir, TarballUnpackError, my_dir)
            assert (
                str(exc.value)
                == f"An error occurred while unpacking {my_dir}: Command '{my_command}' timed out after 43 seconds"
            )

    def test_tarball_subprocess_run_with_returncode(self, monkeypatch):
        """Test to check the subprocess_run functionality of the Tarball when
        returncode value is not zero"""
        my_command = "mycommand"

        def mock_run(args, **kwargs):
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
            assert (
                str(exc.value)
                == f"An error occurred while unpacking {my_dir.name}: {my_command} exited with status 1:  'Some error unpacking tarball'"
            )

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
                            f121_sym -> /tmp/<dir_name>/subdir1/subdir15
                            f122_sym -> ./bad_subdir/nonexixtent_file.txt
                        subdir13/
                            f131_sym -> /etc/passwd
                        subdir14/
                            subdir141/
                                f1411.txt
                                f1412_sym -> /tmp/<dir_name>/subdir1/f11.txt
                                f1413_sym -> ../subdir141
                                f1414_sym -> ./f1411.txt
                                f1415_sym -> ./f1412_sym
                        f11.txt
                        f12_sym -> ../../<dir_name>
                    f1.json


            Generated cache map

            {
                'dir_name': {
                    'details': <cache_manager.FileInfo object>,
                    'children': {
                        'f1.json': {'details': <cache_manager.FileInfo object>},
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
            for i in range(1, 4):
                (sub_dir / "subdir1" / f"subdir1{i}").mkdir(parents=True, exist_ok=True)
            (sub_dir / "subdir1" / "f11.txt").touch()
            (sub_dir / "subdir1" / "subdir14" / "subdir141").mkdir(
                parents=True, exist_ok=True
            )
            (sub_dir / "subdir1" / "subdir14" / "subdir141" / "f1411.txt").touch()
            sym_file = sub_dir / "subdir1" / "f12_sym"
            os.symlink(Path("../..") / dir_name, sym_file)
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

            return sub_dir

    class MockTarball:
        def __init__(self, path: Path, controller: Controller):
            self.name = Dataset.stem(path)
            self.tarball_path = path
            self.cache = controller.cache / "ABC"
            self.unpacked = None

    def test_unpack_tar_subprocess_exception(self, monkeypatch):
        """Show that, when unpacking of the Tarball fails and raises
        an Exception it is handled successfully."""
        tar = Path("/mock/A.tar.xz")
        cache = Path("/mock/.cache")
        rmtree_called = False

        def mock_rmtree(path: Path, ignore_errors=False):
            nonlocal rmtree_called
            rmtree_called = True

            assert ignore_errors
            assert path == cache / "ABC"

        def mock_run(command, dir_path, exception, dir_p):
            verb = "tar"
            assert command.startswith(verb)
            raise exception(dir_p, subprocess.TimeoutExpired(verb, 43))

        with monkeypatch.context() as m:
            m.setattr(Path, "mkdir", lambda path, parents: None)
            m.setattr(Tarball, "subprocess_run", staticmethod(mock_run))
            m.setattr(shutil, "rmtree", mock_rmtree)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(tar, Controller(Path("/mock/archive"), cache, None))
            with pytest.raises(TarballUnpackError) as exc:
                tb.unpack()
            assert (
                str(exc.value)
                == f"An error occurred while unpacking {tar}: Command 'tar' timed out after 43 seconds"
            )
            assert exc.type == TarballUnpackError
            assert rmtree_called

    def test_unpack_find_subprocess_exception(self, monkeypatch):
        """Show that, when permission change of the Tarball fails and raises
        an Exception it is handled successfully."""
        tar = Path("/mock/A.tar.xz")
        cache = Path("/mock/.cache")
        rmtree_called = True

        def mock_rmtree(path: Path, ignore_errors=False):
            nonlocal rmtree_called
            rmtree_called = True

            assert ignore_errors
            assert path == cache / "ABC"

        def mock_run(command, dir_path, exception, dir_p):
            verb = "find"
            if command.startswith(verb):
                raise exception(dir_p, subprocess.TimeoutExpired(verb, 43))
            else:
                assert command.startswith("tar")

        with monkeypatch.context() as m:
            m.setattr(Path, "mkdir", lambda path, parents: None)
            m.setattr(Tarball, "subprocess_run", staticmethod(mock_run))
            m.setattr(shutil, "rmtree", mock_rmtree)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(tar, Controller(Path("/mock/archive"), cache, None))

            with pytest.raises(TarballModeChangeError) as exc:
                tb.unpack()
            assert (
                str(exc.value)
                == f"An error occurred while changing file permissions of {cache / 'ABC'}: Command 'find' timed out after 43 seconds"
            )
            assert exc.type == TarballModeChangeError
            assert rmtree_called

    def test_unpack_success(self, monkeypatch):
        """Test to check the unpacking functionality of the CacheManager"""
        tar = Path("/mock/A.tar.xz")
        cache = Path("/mock/.cache")
        call = list()

        def mock_run(args, **kwargs):
            call.append(args[0])

            tar_target = "--file=" + str(tar)
            assert args[0] == "find" or args[0] == "tar" and tar_target in args
            return subprocess.CompletedProcess(
                args, returncode=0, stdout="Successfully Unpacked!", stderr=None
            )

        with monkeypatch.context() as m:
            m.setattr(Path, "mkdir", lambda path, parents: None)
            m.setattr(subprocess, "run", mock_run)
            m.setattr(Path, "resolve", lambda path, strict: path)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(tar, Controller(Path("/mock/archive"), cache, None))
            tb.unpack()
            assert call == ["tar", "find"]
            assert tb.unpacked == cache / "ABC" / tb.name

    def test_cache_map_success(self, monkeypatch, tmp_path):
        """Test to build the cache map of the root directory"""
        tar = Path("/mock/dir_name.tar.xz")
        cache = Path("/mock/.cache")

        with monkeypatch.context() as m:
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(tar, Controller(Path("/mock/archive"), cache, None))
            tar_dir = TestCacheManager.MockController.generate_test_result_tree(
                tmp_path, "dir_name"
            )
            tb.cache_map(tar_dir)
            assert (
                tb.cachemap["dir_name"]["children"]["subdir1"]["details"].name
                == "subdir1"
            )
            assert (
                tb.cachemap["dir_name"]["children"]["subdir1"]["children"]["subdir14"][
                    "children"
                ]["subdir141"]["children"]["f1412_sym"]["details"].type
                == CacheType.SYMLINK
            )

    @pytest.mark.parametrize(
        "file_path, expected_msg",
        [
            (
                "/dir_name/subdir1/f11.txt",
                "The directory path '/dir_name/subdir1/f11.txt' is an absolute path, we expect relative path to the root directory.",
            ),
            (
                "dir_name/subdir1/subdir11/../f11.txt",
                "File/directory '..' in path dir_name/subdir1/subdir11/../f11.txt not found in cache.",
            ),
            (
                "dir_name/subdir1/subdir14/subdir1",
                "File/directory 'subdir1' in path dir_name/subdir1/subdir14/subdir1 not found in cache.",
            ),
            (
                "dir_name/ne_dir",
                "File/directory 'ne_dir' in path dir_name/ne_dir not found in cache.",
            ),
            (
                "dir_name/subdir1/ne_file",
                "File/directory 'ne_file' in path dir_name/subdir1/ne_file not found in cache.",
            ),
            (
                "dir_name/ne_dir/ne_file",
                "File/directory 'ne_dir' in path dir_name/ne_dir/ne_file not found in cache.",
            ),
            (
                "dir_name/subdir1/f11.txt/ne_subdir",
                "Found a file 'f11.txt' where a directory was expected in path dir_name/subdir1/f11.txt/ne_subdir",
            ),
            (
                "dir_name/subdir1/subdir14/subdir141/f1412_sym/ne_file",
                "Found a file 'f1412_sym' where a directory was expected in path dir_name/subdir1/subdir14/subdir141/f1412_sym/ne_file",
            ),
        ],
    )
    def test_cache_map_bad_dir_path(
        self, monkeypatch, tmp_path, file_path, expected_msg
    ):
        """Test to check bad directory or file path"""
        tar = Path("/mock/dir_name.tar.xz")
        cache = Path("/mock/.cache")

        with monkeypatch.context() as m:
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(tar, Controller(Path("/mock/archive"), cache, None))
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
                Path("dir_name"),
                CacheType.DIRECTORY,
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
                Path("subdir1/f11.txt"),
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
        ],
    )
    def test_cache_map_traverse_cmap(
        self,
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
            tb = Tarball(tar, Controller(Path("/mock/archive"), cache, None))
            tar_dir = TestCacheManager.MockController.generate_test_result_tree(
                tmp_path, "dir_name"
            )
            tb.cache_map(tar_dir)

            # Hack for absolute path
            if str(location).endswith("f1412_sym"):
                resolve_path = tar_dir / resolve_path

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
        self, monkeypatch, tmp_path, file_path, expected_msg
    ):
        """Test to check if the info returned by the cachemap is correct"""
        tar = Path("/mock/dir_name.tar.xz")
        cache = Path("/mock/.cache")

        with monkeypatch.context() as m:
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            m.setattr(Controller, "__init__", TestCacheManager.MockController.__init__)
            tb = Tarball(tar, Controller(Path("/mock/archive"), cache, None))
            tar_dir = TestCacheManager.MockController.generate_test_result_tree(
                tmp_path, "dir_name"
            )
            tb.cache_map(tar_dir)

            # test get_info with random path
            file_info = tb.get_info(Path(file_path))
            assert file_info == expected_msg

    def test_find(
        self, selinux_enabled, server_config, make_logger, tarball, monkeypatch
    ):
        """
        Create a dataset, check the cache manager state, and test that we can find it
        through the various supported methods.
        """

        def mock_run(args, **kwargs):
            """Prevents the Tarball contents from actually being unpacked"""
            return subprocess.CompletedProcess(
                args, returncode=0, stdout="Success!", stderr=None
            )

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
            cm["foobar"]
        assert (
            str(exc.value)
            == "The dataset tarball named 'foobar' is not present in the cache manager"
        )

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
        assert (
            str(exc.value)
            == "The dataset tarball named 'foobar' is not present in the cache manager"
        )
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

        def mock_run(args, **kwargs):
            """Prevents the Tarball contents from actually being unpacked"""
            return subprocess.CompletedProcess(
                args, returncode=0, stdout="Success!", stderr=None
            )

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

        tarfile = archive / source_tarball.name
        md5file = archive / source_md5.name
        assert tarfile.exists()
        assert md5file.exists()

        assert md5 == md5file.read_text()
        hash = hashlib.md5()
        hash.update(tarfile.read_bytes())
        assert md5 == hash.hexdigest()

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
        cm.uncache(md5)
        assert not cache.exists()

        # Now that we have all that setup, delete the dataset
        cm.delete(md5)
        assert not archive.exists()
        assert not cm.controllers
        assert not cm.datasets
