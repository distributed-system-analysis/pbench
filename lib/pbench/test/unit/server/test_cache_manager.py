import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

import pytest

from pbench.server.cache_manager import (
    BadFilename,
    CacheManager,
    DuplicateTarball,
    MetadataError,
    Tarball,
    TarballModeChangeError,
    TarballNotFound,
    TarballUnpackError,
)
from pbench.server.database.models.datasets import Dataset, DatasetBadName
from pbench.server.globals import server


@pytest.fixture(scope="function", autouse=True)
def file_sweeper(server_config):
    """
    Make sure that the required directory trees exist before each test case,
    and clean up afterwards.
    """
    trees = [server.config.ARCHIVE, server.config.INCOMING, server.config.RESULTS]

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
    def test_create(self, server_config, server_logger):
        """
        Create an empty CacheManager object and check the properties
        """
        cm = CacheManager()
        assert cm is not None
        assert not cm.datasets  # No datasets expected
        assert not cm.tarballs  # No datasets expected
        assert not cm.controllers  # No controllers expected

        temp = re.compile(r"^(.*)/srv/pbench")
        match = temp.match(str(cm.archive_root))
        root = match.group(1)
        assert str(cm.archive_root) == root + "/srv/pbench/archive/fs-version-001"
        assert str(cm.incoming_root) == root + "/srv/pbench/public_html/incoming"
        assert str(cm.results_root) == root + "/srv/pbench/public_html/results"

    def test_discover_empties(self, server_config, server_logger):
        """
        Full discovery with no controllers or datasets
        """
        cm = CacheManager()
        cm.full_discovery()
        assert not cm.datasets  # No datasets expected
        assert not cm.tarballs  # No datasets expected
        assert not cm.controllers  # No controllers expected

    def test_empty_controller(self, server_config, server_logger):
        """
        Discover a "controller" directory with no datasets
        """
        cm = CacheManager()
        test_controller = cm.archive_root / "TEST"
        test_controller.mkdir()
        cm.full_discovery()
        assert not cm.datasets  # No datasets expected
        assert not cm.tarballs  # No datasets expected
        assert list(cm.controllers.keys()) == ["TEST"]

    def test_clean_empties(self, server_config, server_logger):
        """
        Test that empty controller directories are removed
        """
        cm = CacheManager()
        controllers = ["PLUGH", "XYZZY"]
        roots = [cm.archive_root, cm.incoming_root, cm.results_root]
        for c in controllers:
            for r in roots:
                (r / c).mkdir(parents=True)
        cm.full_discovery()
        ctrls = sorted(cm.controllers)
        assert ctrls == controllers

        for c in controllers:
            cm._clean_empties(c)
        assert not cm.controllers
        for c in controllers:
            for r in roots:
                assert not (r / c).exists()

    def test_metadata(
        self, monkeypatch, selinux_disabled, server_config, make_logger, tarball
    ):
        """
        Test behavior of the metadata file when key/value are not present.
        """

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

        source_tarball, source_md5, md5 = tarball
        cm = CacheManager(server_config, make_logger)
        # fetching metadata from metadata.log file and key/value not
        # being there should result in a MetadataError
        tar_name = source_tarball.name.removesuffix(".tar.xz")

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: \"'filename {tar_name}/metadata.log not found'\""
        monkeypatch.setattr(tarfile.TarFile, "extractfile", fake_extract_file)
        with pytest.raises(MetadataError) as exc:
            cm.create(source_tarball)
        assert str(exc.value) == expected_metaerror

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: 'Invalid Tarfile'"
        monkeypatch.setattr(tarfile, "open", fake_tarfile_open)
        with pytest.raises(MetadataError) as exc:
            cm.create(source_tarball)
        assert str(exc.value) == expected_metaerror

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: \"'run'\""
        monkeypatch.setattr(Tarball, "_get_metadata", fake_metadata)
        with pytest.raises(MetadataError) as exc:
            cm.create(source_tarball)
        assert str(exc.value) == expected_metaerror

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: \"'controller'\""
        monkeypatch.setattr(Tarball, "_get_metadata", fake_metadata_run)
        with pytest.raises(MetadataError) as exc:
            cm.create(source_tarball)
        assert str(exc.value) == expected_metaerror

        expected_metaerror = f"A problem occurred processing metadata.log from {source_tarball!s}: 'no controller value'"
        monkeypatch.setattr(Tarball, "_get_metadata", fake_metadata_controller)
        with pytest.raises(MetadataError) as exc:
            cm.create(source_tarball)
        assert str(exc.value) == expected_metaerror

        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)
        cm.create(source_tarball)
        tarball = cm.find_dataset(md5)

        assert tarball.metadata == fake_get_metadata(tarball.tarball_path)

    def test_create_bad(
        self, monkeypatch, selinux_disabled, server_config, server_logger, tarball
    ):
        """
        Test several varieties of dataset errors:

        1) Attempt to create a new dataset from an MD5 file
        2) Attempt to create a new dataset from a non-existent file
        3) Attempt to create a dataset that already exists
        """
        cm = CacheManager()
        source_tarball, source_md5, md5 = tarball
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
        self, monkeypatch, selinux_disabled, server_config, server_logger, tarball
    ):
        """
        Test behavior when we try to create a new dataset but the tarball file
        name already exists
        """
        cm = CacheManager()
        source_tarball, source_md5, md5 = tarball
        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)

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
            my_dir = "my_dir"

            with pytest.raises(TarballUnpackError) as exc:
                Tarball.subprocess_run(command, my_dir, TarballUnpackError, my_dir)
            assert (
                str(exc.value)
                == f"An error occurred while unpacking {my_dir}: {my_command} exited with status 1:  'Some error unpacking tarball'"
            )

    def test_tarball_subprocess_run_success(self, monkeypatch):
        """Test to check the successful run of subprocess_run functionality of the Tarball."""
        my_command = "mycommand"
        my_dir = "my_dir"
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

    def test_tarball_move_src(self, monkeypatch):
        """Show that, when source directory for moving results is not present and
        raises an Exception, it is handled successfully."""

        def mock_move(src: Path, dest: Path):
            raise FileNotFoundError(f"No such file or directory: '{src}'")

        with monkeypatch.context() as m:
            m.setattr(shutil, "move", mock_move)
            tar = "tarball"
            unpacking_dir = "src_dir"
            unpacked_dir = "dest_dir"
            with pytest.raises(TarballUnpackError) as exc:
                Tarball.do_move(unpacking_dir, unpacked_dir, tar)
            assert (
                str(exc.value)
                == f"An error occurred while unpacking {tar}: Error moving '{unpacking_dir}' to '{unpacked_dir}': No such file or directory: '{unpacking_dir}'"
            )

    def test_tarball_move_dest(self, monkeypatch):
        """Show that, when destination directory for moving results is not present and
        raises an Exception, it is handled successfully."""

        def mock_move(src: Path, dest: Path):
            assert src == "src_dir"
            raise FileNotFoundError(f"No such file or directory: '{dest}'")

        with monkeypatch.context() as m:
            m.setattr(shutil, "move", mock_move)
            tar = "tarball"
            unpacking_dir = "src_dir"
            unpacked_dir = "dest_dir"
            with pytest.raises(TarballUnpackError) as exc:
                Tarball.do_move(unpacking_dir, unpacked_dir, tar)
            assert (
                str(exc.value)
                == f"An error occurred while unpacking {tar}: Error moving '{unpacking_dir}' to '{unpacked_dir}': No such file or directory: '{unpacked_dir}'"
            )

    def test_tarball_move_success(self, monkeypatch):
        """Show the successful run of move function."""
        tar = "tarball"
        move_called = False

        def mock_move(src: Path, dest: Path):
            nonlocal move_called
            move_called = True
            assert src == "src_dir"
            assert dest == "dest_dir"

        with monkeypatch.context() as m:
            m.setattr(shutil, "move", mock_move)
            unpacking_dir = "src_dir"
            unpacked_dir = "dest_dir"
            Tarball.do_move(unpacking_dir, unpacked_dir, tar)
            assert move_called

    class MockTarball:
        def __init__(self, path):
            self.name = "A"
            self.tarball_path = Path("/mock/A.tar.xz")

    def test_unpack_tar_subprocess_exception(self, monkeypatch):
        """Show that, when unpacking of the Tarball fails and raises
        an Exception it is handled successfully."""
        tar = Path("/mock/A.tar.xz")
        tarball_name = tar.name.removesuffix(".tar.xz")
        incoming = Path("/mock/incoming/ABC")
        results = Path("/mock/results/ABC")
        rmtree_called = False

        def mock_rmtree(path: Path, ignore_errors=False):
            nonlocal rmtree_called
            rmtree_called = True

            assert ignore_errors
            assert path == incoming / f"{tarball_name}.unpack"

        def mock_run(command, dir_path, exception, dir_p):
            verb = "tar"
            assert command.startswith(verb)
            raise exception(dir_p, subprocess.TimeoutExpired(verb, 43))

        with monkeypatch.context() as m:
            m.setattr(Path, "mkdir", lambda path, parents: None)
            m.setattr(Tarball, "subprocess_run", staticmethod(mock_run))
            m.setattr(shutil, "rmtree", mock_rmtree)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            tb = Tarball(tar)
            with pytest.raises(TarballUnpackError) as exc:
                tb.unpack(incoming, results)
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
        tarball_name = tar.name.removesuffix(".tar.xz")
        incoming = Path("/mock/incoming/ABC")
        results = Path("/mock/results/ABC")
        unpack_dir = incoming / f"{tarball_name}.unpack"
        rmtree_called = True

        def mock_rmtree(path: Path, ignore_errors=False):
            nonlocal rmtree_called
            rmtree_called = True

            assert ignore_errors
            assert path == unpack_dir

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
            tb = Tarball(tar)

            with pytest.raises(TarballModeChangeError) as exc:
                tb.unpack(incoming, results)
            assert (
                str(exc.value)
                == f"An error occurred while changing file permissions of {unpack_dir}: Command 'find' timed out after 43 seconds"
            )
            assert exc.type == TarballModeChangeError
            assert rmtree_called

    def test_unpack_move_error(self, monkeypatch):
        """Show that, when something goes wrong while moving results and it
        raises an Exception, it is handled successfully."""
        tar = Path("/mock/A.tar.xz")
        tarball_name = tar.name.removesuffix(".tar.xz")
        incoming = Path("/mock/incoming/ABC")
        results = Path("/mock/results/ABC")
        rmtree_called = False

        def mock_rmtree(path: Path, ignore_errors=False):
            nonlocal rmtree_called
            rmtree_called = True

            assert ignore_errors
            assert path == incoming / f"{tarball_name}.unpack"

        def mock_move(src: Path, dest: Path, ctx: Path):
            raise FileNotFoundError(f"No such file or directory: '{src}'")

        with monkeypatch.context() as m:
            m.setattr(Path, "mkdir", lambda path, parents: None)
            m.setattr(Tarball, "subprocess_run", lambda *args: None)
            m.setattr(Tarball, "do_move", staticmethod(mock_move))
            m.setattr(shutil, "rmtree", mock_rmtree)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            tb = Tarball(tar)

            unpacking_dir = incoming / f"{tarball_name}.unpack" / tarball_name
            with pytest.raises(Exception) as exc:
                tb.unpack(incoming, results)
            assert str(exc.value) == f"No such file or directory: '{unpacking_dir}'"
            assert rmtree_called

    def test_unpack_success(self, monkeypatch):
        """Test to check the unpacking functionality of the CacheManager"""
        tar = Path("/mock/A.tar.xz")
        tarball_name = tar.name.removesuffix(".tar.xz")
        incoming = Path("/mock/incoming/ABC")
        results = Path("/mock/results/ABC")
        call = list()

        def mock_rmtree(path: Path, ignore_errors=False):
            call.append("rmtree")
            assert ignore_errors
            assert path == incoming / f"{tarball_name}.unpack"

        def mock_symlink(path: Path, link: Path):
            call.append("symlink_to")
            assert path == results / tarball_name
            assert link == incoming / tarball_name

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
            m.setattr(Tarball, "do_move", lambda *args: None)
            m.setattr(shutil, "rmtree", mock_rmtree)
            m.setattr(Path, "symlink_to", mock_symlink)
            m.setattr(Tarball, "__init__", TestCacheManager.MockTarball.__init__)
            tb = Tarball(tar)
            tb.unpack(incoming, results)
            assert call == ["tar", "find", "rmtree", "symlink_to"]
            assert tb.unpacked == incoming / tb.name
            assert tb.results_link == results / tb.name

    def test_find(
        self, monkeypatch, selinux_enabled, server_config, server_logger, tarball
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
        cm = CacheManager()
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

        assert cm.controllers == {controller.name: controller}
        assert cm.datasets == {md5: tarball}

        # It hasn't been unpacked
        assert tarball.unpacked is None
        assert tarball.results_link is None

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
        assert tarball.unpacked == controller.incoming / tarball.name
        assert tarball.results_link == controller.results / tarball.name

        # We should be able to find the tarball even in a new cache manager
        # that hasn't been fully discovered.
        new = CacheManager()
        assert md5 not in new

        tarball = new.find_dataset(md5)
        assert tarball
        assert tarball.name == dataset_name

        # We should have discovered the INCOMING and RESULTS data automagically
        assert tarball.unpacked == controller.incoming / tarball.name
        assert tarball.results_link == controller.results / tarball.name

        # We should have just one controller and one tarball
        assert tarball.resource_id == md5
        assert list(new.controllers) == ["ABC"]
        assert list(new.datasets) == [md5]
        assert list(new.tarballs) == [dataset_name]

    def test_lifecycle(
        self, selinux_enabled, server_config, server_logger, tarball, monkeypatch
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
        cm = CacheManager()
        archive = cm.archive_root / "ABC"
        incoming = cm.incoming_root / "ABC"
        results = cm.results_root / "ABC"
        monkeypatch.setattr(Tarball, "_get_metadata", fake_get_metadata)

        # None of the controller directories should exist yet
        assert not archive.exists()
        assert not incoming.exists()
        assert not results.exists()

        # Create a dataset in the cache manager from our source tarball
        cm.create(source_tarball)

        # Expect the archive directory was created, but we haven't unpacked so
        # incoming and results should not exist.
        assert archive.is_dir()
        assert not incoming.exists()
        assert not results.exists()

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
        incoming_dir = incoming / dataset_name
        results_link = results / dataset_name
        cm.unpack(md5)
        assert incoming_dir.is_dir()
        assert results_link.is_symlink()
        assert results_link.samefile(incoming_dir)

        assert cm.datasets[md5].unpacked == incoming_dir
        assert cm.datasets[md5].results_link == results_link

        # Re-discover, with all the files in place, and compare
        newcm = CacheManager()
        newcm.full_discovery()

        assert newcm.archive_root == cm.archive_root
        assert newcm.incoming_root == cm.incoming_root
        assert newcm.results_root == cm.results_root
        assert sorted(newcm.controllers) == sorted(cm.controllers)
        assert sorted(newcm.datasets) == sorted(cm.datasets)
        assert sorted(newcm.tarballs) == sorted(cm.tarballs)
        for controller in cm.controllers.values():
            other = newcm.controllers[controller.name]
            assert controller.name == other.name
            assert controller.path == other.path
            assert sorted(controller.datasets) == sorted(other.datasets)
            assert sorted(controller.tarballs) == sorted(other.tarballs)
        for tarball in cm.datasets.values():
            other = newcm.datasets[tarball.resource_id]
            assert tarball.name == other.name
            assert tarball.resource_id == other.resource_id
            assert tarball.controller_name == other.controller_name
            assert tarball.tarball_path == other.tarball_path
            assert tarball.md5_path == other.md5_path
            assert tarball.unpacked == other.unpacked
            assert tarball.results_link == other.results_link

        # Remove the unpacked tarball, and confirm that the directory and link
        # are removed.
        cm.uncache(md5)
        assert not results_link.exists()
        assert not incoming_dir.exists()

        # Now that we have all that setup, delete the dataset
        cm.delete(md5)
        assert not archive.exists()
        assert not cm.controllers
        assert not cm.datasets
