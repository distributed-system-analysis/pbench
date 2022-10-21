import hashlib
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from pbench.common.logger import get_pbench_logger
from pbench.server.database.models.datasets import Dataset, DatasetBadName
from pbench.server.cache_manager import (
    BadFilename,
    DuplicateTarball,
    CacheManager,
    Tarball,
    TarballModeChangeError,
    TarballNotFound,
    TarballUnpackError,
)


@pytest.fixture()
def make_logger(server_config):
    """
    Construct a Pbench Logger object
    """
    return get_pbench_logger("TEST", server_config)


@pytest.fixture(scope="function", autouse=True)
def file_sweeper(server_config):
    """
    Make sure that the required directory trees exist before each test case,
    and clean up afterwards.
    """
    trees = [server_config.ARCHIVE, server_config.INCOMING, server_config.RESULTS]

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


class TestCacheManager:
    def test_create(self, server_config, make_logger):
        """
        Create an empty CacheManager object and check the properties
        """
        tree = CacheManager(server_config, make_logger)
        assert tree is not None
        assert not tree.datasets  # No datasets expected
        assert not tree.tarballs  # No datasets expected
        assert not tree.controllers  # No controllers expected

        temp = re.compile(r"^(.*)/srv/pbench")
        match = temp.match(str(tree.archive_root))
        root = match.group(1)
        assert str(tree.archive_root) == root + "/srv/pbench/archive/fs-version-001"
        assert str(tree.incoming_root) == root + "/srv/pbench/public_html/incoming"
        assert str(tree.results_root) == root + "/srv/pbench/public_html/results"

    def test_discover_empties(self, server_config, make_logger):
        """
        Full discovery with no controllers or datasets
        """
        tree = CacheManager(server_config, make_logger)
        tree.full_discovery()
        assert not tree.datasets  # No datasets expected
        assert not tree.tarballs  # No datasets expected
        assert not tree.controllers  # No controllers expected

    def test_empty_controller(self, server_config, make_logger):
        """
        Discover a "controller" directory with no datasets
        """
        tree = CacheManager(server_config, make_logger)
        test_controller = tree.archive_root / "TEST"
        test_controller.mkdir()
        tree.full_discovery()
        assert not tree.datasets  # No datasets expected
        assert not tree.tarballs  # No datasets expected
        assert list(tree.controllers.keys()) == ["TEST"]

    def test_clean_empties(self, server_config, make_logger):
        """
        Test that empty controller directories are removed
        """
        tree = CacheManager(server_config, make_logger)
        controllers = ["PLUGH", "XYZZY"]
        roots = [tree.archive_root, tree.incoming_root, tree.results_root]
        for c in controllers:
            for r in roots:
                (r / c).mkdir(parents=True)
        tree.full_discovery()
        ctrls = sorted(tree.controllers)
        assert ctrls == controllers

        for c in controllers:
            tree._clean_empties(c)
        assert not tree.controllers
        for c in controllers:
            for r in roots:
                assert not (r / c).exists()

    def test_create_bad(self, selinux_disabled, server_config, make_logger, tarball):
        """
        Test several varieties of dataset errors:

        1) Attempt to create a new dataset from an MD5 file
        2) Attempt to create a new dataset from a non-existent file
        3) Attempt to create a dataset that already exists
        """

        source_tarball, source_md5, md5 = tarball
        tree = CacheManager(server_config, make_logger)

        # Attempting to create a dataset from the md5 file should result in
        # a bad filename error
        with pytest.raises(DatasetBadName) as exc:
            tree.create("ABC", source_md5)
        assert exc.value.name == str(source_md5)

        tree.create("ABC", source_tarball)

        # The create will remove the source files, so trying again should
        # result in an error.
        with pytest.raises(BadFilename) as exc:
            tree.create("ABC", source_md5)
        assert exc.value.path == str(source_md5)

        # Attempting to create the same dataset again (from the archive copy)
        # should fail with a duplicate dataset error.
        tarball = tree.find_dataset(md5)
        with pytest.raises(DuplicateTarball) as exc:
            tree.create("ABC", tarball.tarball_path)
        assert (
            str(exc.value)
            == "A dataset tarball named 'pbench-user-benchmark_some + config_2021.05.01T12.42.42' is already present in the cache manager"
        )
        assert exc.value.tarball == tarball.name

    def test_duplicate(self, selinux_disabled, server_config, make_logger, tarball):
        """
        Test behavior when we try to create a new dataset but the tarball file
        name already exists
        """

        source_tarball, source_md5, md5 = tarball
        tree = CacheManager(server_config, make_logger)

        # Create a tarball file in the expected destination directory
        controller = tree.archive_root / "ABC"
        controller.mkdir()
        (controller / source_tarball.name).write_text("Send in the clones")

        # Attempting to create a dataset from the md5 file should result in
        # a duplicate dataset error
        with pytest.raises(DuplicateTarball) as exc:
            tree.create("ABC", source_tarball)
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
        self, selinux_enabled, server_config, make_logger, tarball, monkeypatch
    ):
        """
        Create a dataset, check the tree state, and test that we can find it
        through the various supported methods.
        """

        def mock_run(args, **kwargs):
            """Prevents the Tarball contents from actually being unpacked"""
            return subprocess.CompletedProcess(
                args, returncode=0, stdout="Success!", stderr=None
            )

        source_tarball, source_md5, md5 = tarball
        dataset_name = Dataset.stem(source_tarball)
        tree = CacheManager(server_config, make_logger)
        tree.create("ABC", source_tarball)

        # The original files should have been removed
        assert not source_tarball.exists()
        assert not source_md5.exists()

        tarball = tree.find_dataset(md5)
        assert tarball
        assert tarball.name == dataset_name
        assert tarball.resource_id == md5

        # Test __getitem__
        assert tarball == tree[md5]
        with pytest.raises(TarballNotFound) as exc:
            tree["foobar"]
        assert (
            str(exc.value)
            == "The dataset tarball named 'foobar' is not present in the cache manager"
        )

        # Test __contains__
        assert md5 in tree
        assert "foobar" not in tree

        # There should be nothing else in the tree
        controller = tarball.controller

        assert tree.controllers == {controller.name: controller}
        assert tree.datasets == {md5: tarball}

        # It hasn't been unpacked
        assert tarball.unpacked is None
        assert tarball.results_link is None

        # Try to find a dataset that doesn't exist
        with pytest.raises(TarballNotFound) as exc:
            tree.find_dataset("foobar")
        assert (
            str(exc.value)
            == "The dataset tarball named 'foobar' is not present in the cache manager"
        )
        assert exc.value.tarball == "foobar"

        # Unpack the dataset, creating INCOMING and RESULTS links
        tree.unpack(md5)
        assert tarball.unpacked == controller.incoming / tarball.name
        assert tarball.results_link == controller.results / tarball.name

        # We should be able to find the tarball even in a new cache manager
        # that hasn't been fully discovered.
        new = CacheManager(server_config, make_logger)
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
        tree = CacheManager(server_config, make_logger)
        archive = tree.archive_root / "ABC"
        incoming = tree.incoming_root / "ABC"
        results = tree.results_root / "ABC"

        # None of the controller directories should exist yet
        assert not archive.exists()
        assert not incoming.exists()
        assert not results.exists()

        # Create a dataset in the cache manager from our source tarball
        tree.create("ABC", source_tarball)

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

        todo_state = archive / "TODO" / tarfile.name
        assert todo_state.is_symlink()
        assert todo_state.samefile(tarfile)

        assert md5 == md5file.read_text()
        hash = hashlib.md5()
        hash.update(tarfile.read_bytes())
        assert md5 == hash.hexdigest()

        assert list(tree.controllers.keys()) == ["ABC"]
        dataset_name = source_tarball.name[:-7]
        assert list(tree.tarballs) == [dataset_name]
        assert list(tree.datasets) == [md5]

        # Now "unpack" the tarball and check that the incoming directory and
        # results link are set up.
        incoming_dir = incoming / dataset_name
        results_link = results / dataset_name
        tree.unpack(md5)
        assert incoming_dir.is_dir()
        assert results_link.is_symlink()
        assert results_link.samefile(incoming_dir)

        assert tree.datasets[md5].unpacked == incoming_dir
        assert tree.datasets[md5].results_link == results_link

        # Re-discover, with all the files in place, and compare
        newtree = CacheManager(server_config, make_logger)
        newtree.full_discovery()

        assert newtree.archive_root == tree.archive_root
        assert newtree.incoming_root == tree.incoming_root
        assert newtree.results_root == tree.results_root
        assert sorted(newtree.controllers) == sorted(tree.controllers)
        assert sorted(newtree.datasets) == sorted(tree.datasets)
        assert sorted(newtree.tarballs) == sorted(tree.tarballs)
        for controller in tree.controllers.values():
            other = newtree.controllers[controller.name]
            assert controller.name == other.name
            assert controller.path == other.path
            assert sorted(controller.datasets) == sorted(other.datasets)
            assert sorted(controller.tarballs) == sorted(other.tarballs)
        for tarball in tree.datasets.values():
            other = newtree.datasets[tarball.resource_id]
            assert tarball.name == other.name
            assert tarball.resource_id == other.resource_id
            assert tarball.controller_name == other.controller_name
            assert tarball.tarball_path == other.tarball_path
            assert tarball.md5_path == other.md5_path
            assert tarball.unpacked == other.unpacked
            assert tarball.results_link == other.results_link

        # Remove the unpacked tarball, and confirm that the directory and link
        # are removed.
        tree.uncache(md5)
        assert not results_link.exists()
        assert not incoming_dir.exists()

        # Now that we have all that setup, delete the dataset
        tree.delete(md5)
        assert not archive.exists()
        assert not tree.controllers
        assert not tree.datasets
