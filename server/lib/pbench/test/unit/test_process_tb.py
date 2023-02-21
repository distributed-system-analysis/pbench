import errno
import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union

import pbench.process_tb
import pytest

# Create module level bindings from the module import for convenience.
ProcessTb = pbench.process_tb.ProcessTb
Results = pbench.process_tb.Results


@pytest.fixture
def file_system(monkeypatch):
    """Provide a mock'd up file system where all the behaviors are handled via
    Path method mocks.

    The real file system layout looks something like:

        /srv/pbench/
            archive/
                fs-version-001/
                    <controllers>/
                        TO-BACKUP/
                            <tar balls>.tar.xz@
                            <tar ball md5s>.tar.xz.md5@
                        TO-INDEX/
                        TO-UNPACK/
                            <tar balls>.tar.xz@
                            <tar ball md5s>.tar.xz.md5@
                        <tar balls>.tar.xz
                        <tar ball md5s>.tar.xz.md5
            pbench-results-receive-dir-002/
                <controllers>
                    <tar balls>.tar.xz
                    <tar ball md5s>.tar.xz.md5
            quarantine/
                duplicates-002/
                    <controllers>/
                        <tar balls>.tar.xz
                        <tar ball md5s>.tar.xz.md5
                md5-002/
                    <controllers>/
                        <tar balls>.tar.xz
                        <tar ball md5s>.tar.xz.md5

    Each test provides a file system hierarchy dictionary with the expected
    layout to start the test.  The provided Path mock operates on that
    dictionary to read and update it as needed.

    A "directory" is represented by a key/value pair where the value is a
    dictionary.  A "file" is a key/value pair where the value is a list of
    strings, and a "symlink" is where the value is a string containing the
    "link".
    """
    # The MockFileSystemPath "closes" over this dictionary so that callers can
    # construct their initial setup.
    file_system_hier: dict[str, Union[str, dict]] = {"/": {}}

    class MockFileSystemPath:
        hier = file_system_hier
        trace = []

        class InternalError(Exception):
            def __init__(self, msg):
                self.msg = msg

            def __str__(self) -> str:
                return f"MockFileSystemPath - INTERNAL ERROR - {self.msg}"

        def __init__(self, name: str, val: Optional[str] = None):
            """Approximate mocked behavior of a Path object where an actual Path
            object is used to provide the `name` and `parts` fields.
            """
            p = Path(name)
            self._str = str(p)
            self.parts = p.parts
            self.name = p.name
            if not p.name:
                self.parent = self
            else:
                self.parent = MockFileSystemPath(str(p.parent))

        def _is_root(self) -> bool:
            if not self.name:
                # "/" always exists
                if len(self.parts) != 1 or self.parts[0] != "/":
                    raise self.InternalError("invalid root object")
                return True
            if self.name != self.parts[-1]:
                raise self.InternalError("invalid object, name does not end parts")
            return False

        def _lookup_entry(self) -> Tuple[dict, Union[dict, list, str]]:
            if self._is_root():
                return file_system_hier["/"], file_system_hier["/"]
            curr = file_system_hier
            parent = None
            for el in self.parts:
                parent = curr
                try:
                    curr = parent[el]
                except KeyError:
                    curr = None
                    break
            if (
                curr is not None
                and not isinstance(curr, dict)
                and not isinstance(curr, list)
                and not isinstance(curr, str)
            ):
                raise self.InternalError("unknown object")
            return (parent, curr)

        def exists(self) -> bool:
            parent, entry = self._lookup_entry()
            return entry is not None

        def resolve(self, strict=False) -> "MockFileSystemPath":
            if strict and not self.exists():
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                )
            return MockFileSystemPath(str(self))

        def is_dir(self) -> bool:
            """A directory is determined its entry in the hierarchy being a
            dictionary."""
            parent, entry = self._lookup_entry()
            return isinstance(entry, dict)

        def is_file(self) -> bool:
            """A directory is determined its entry in the hierarchy being a
            list of strings."""
            parent, entry = self._lookup_entry()
            return isinstance(entry, list)

        def mkdir(self, exist_ok=False, parents=False, **kwargs):
            if self._is_root():
                # "/" can't be created
                MockFileSystemPath.trace.append(f"mkdir({self}) EEXIST")
                raise FileExistsError(
                    errno.EEXIST, os.strerror(errno.EEXIST), str(self)
                )
            # We can't use self._lookup_entry() here because mkdir() can create
            # parent directories as it walks the object's "path".
            curr = file_system_hier
            parent = None
            for el in self.parts:
                parent = curr
                if parent is not None and not isinstance(parent, dict):
                    # Non-leaf path element is not a directory
                    MockFileSystemPath.trace.append(f"mkdir({self}) ENOENT")
                    raise FileNotFoundError(
                        errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                    )
                try:
                    curr = parent[el]
                except KeyError:
                    if el == self.name:
                        # Make the directory
                        parent[self.name] = {}
                        MockFileSystemPath.trace.append(f"mkdir({self}) 0")
                        return
                    else:
                        if not parents:
                            MockFileSystemPath.trace.append(f"mkdir({self}) ENOENT")
                            raise FileNotFoundError(
                                errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                            )
                        # Make this non-leaf directory and descend into the
                        # newly created directory
                        curr = parent[el] = {}
            if exist_ok and isinstance(curr, dict):
                MockFileSystemPath.trace.append(f"mkdir({self}) noop")
                return
            MockFileSystemPath.trace.append(f"mkdir({self}) EEXIST")
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(self))

        def touch(self, exist_ok=True, **kwargs):
            if self._is_root():
                # "/" can't be touched
                MockFileSystemPath.trace.append(f"touch({self}) EEXIST")
                raise IsADirectoryError(
                    errno.EISDIR, os.strerror(errno.EISDIR), str(self)
                )
            curr = file_system_hier
            parent = None
            for el in self.parts:
                parent = curr
                if parent is not None and not isinstance(parent, dict):
                    # Non-leaf path element is not a directory
                    MockFileSystemPath.trace.append(f"mkdir({self}) ENOENT")
                    raise FileNotFoundError(
                        errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                    )
                try:
                    curr = parent[el]
                except KeyError:
                    if el == self.name:
                        # Make the file
                        MockFileSystemPath.trace.append(f"touch({self}) 0")
                        parent[self.name] = [""]
                        return
                    else:
                        MockFileSystemPath.trace.append(f"touch({self}) ENOENT")
                        raise FileNotFoundError(
                            errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                        )
            if exist_ok:
                MockFileSystemPath.trace.append(f"touch({self}) noop")
                return
            MockFileSystemPath.trace.append(f"touch({self}) EEXIST")
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(self))

        def symlink_to(self, target, **kwargs):
            if self._is_root():
                # "/" can't be symlinked
                MockFileSystemPath.trace.append(f"symlink_to({self}) EEXIST")
                raise FileExistsError(
                    errno.EEXIST, os.strerror(errno.EEXIST), str(self)
                )
            curr = file_system_hier
            parent = None
            for el in self.parts:
                parent = curr
                if parent is not None and not isinstance(parent, dict):
                    # Non-leaf path element is not a directory
                    MockFileSystemPath.trace.append(f"mkdir({self}) ENOENT")
                    raise FileNotFoundError(
                        errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                    )
                try:
                    curr = parent[el]
                except KeyError:
                    if el == self.name:
                        MockFileSystemPath.trace.append(f"symlink_to({self}) 0")
                        parent[self.name] = str(target)
                        return
                    else:
                        MockFileSystemPath.trace.append(f"symlink_to({self}) ENOENT")
                        raise FileNotFoundError(
                            errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                        )
            MockFileSystemPath.trace.append(f"symlink_to({self}) EEXIST")
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(self))

        def write_text(self, data: str, **kwargs) -> bool:
            parent, entry = self._lookup_entry()
            if entry is None:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                )
            if isinstance(entry, dict):
                raise IsADirectoryError(
                    errno.EISDIR, os.strerror(errno.EISDIR), str(self)
                )
            if isinstance(entry, str):
                # NOTE: writing through symlinks is not supported
                raise OSError(errno.EIO, os.strerror(errno.EIO), str(self))
            parent[self.name] = data.split("\n")

        def read_text(self, **kwargs) -> bool:
            parent, entry = self._lookup_entry()
            if entry is None:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                )
            if isinstance(entry, dict):
                raise IsADirectoryError(
                    errno.EISDIR, os.strerror(errno.EISDIR), str(self)
                )
            if isinstance(entry, str):
                # NOTE: reading through symlinks is not supported
                raise OSError(errno.EIO, os.strerror(errno.EIO), str(self))
            return "\n".join(entry)

        def unlink(self, missing_ok=False, _no_special=False):
            parent, entry = self._lookup_entry()
            if entry is None:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), str(self)
                )
            if isinstance(entry, dict):
                MockFileSystemPath.trace.append(f"unlink({self}) EISDIR")
                raise IsADirectoryError(
                    errno.EISDIR, os.strerror(errno.EISDIR), str(self)
                )
            if not _no_special and self.name in (
                "unlink_fail_tb.tar.xz",
                "unlink_fail_md5.tar.xz.md5",
            ):
                # Special handling
                MockFileSystemPath.trace.append(f"unlink({self}) EIO")
                raise OSError(errno.EIO, os.strerror(errno.EIO), str(self))
            del parent[self.name]

        def glob(self, pattern: str) -> Iterator:
            # Don't get fancy with pattern support, just handle suffixes
            if not pattern.startswith("**/*"):
                raise self.InternalError(f"unsupported pattern '{pattern}'")
            suffix = pattern[4:]
            parent, entry = self._lookup_entry()
            if entry is None or not isinstance(entry, dict):
                return
            # A simple iterative dictionary hierarchy walk.  The subdirs is a
            # stack where each directory encountered is pushed onto the stack
            # and when all directory elements are processed, the top item on
            # the stack is popped off for processing.
            subdirs = [(entry, self)]
            while subdirs:
                curr, parent = subdirs.pop()
                for el, val in sorted(curr.items()):
                    if el.endswith(suffix):
                        yield parent / el
                    if isinstance(val, dict):
                        subdirs.append((val, parent / el))

        def __truediv__(self, arg: str) -> "MockFileSystemPath":
            """Create a new instance of this object with argument added to the
            path.
            """
            curr = "" if self._str == "/" else self._str
            return MockFileSystemPath(f"{curr}/{arg}")

        def __str__(self) -> str:
            return self._str

        def __eq__(self, other: "MockFileSystemPath") -> bool:
            return str(self) == str(other)

        def __lt__(self, other: "MockFileSystemPath") -> bool:
            return str(self) < str(other)

        def __le__(self, other: "MockFileSystemPath") -> bool:
            return str(self) <= str(other)

        def __gt__(self, other: "MockFileSystemPath") -> bool:
            return str(self) > str(other)

        def __ge__(self, other: "MockFileSystemPath") -> bool:
            return str(self) >= str(other)

    def copy(src: Path, dst: Path):
        MockFileSystemPath.trace.append(f"copy({src}, {dst}) begin")
        if not src.is_file():
            MockFileSystemPath.trace.append(f"copy({src}, {dst}) ENOENT")
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(src))
        if not dst.exists():
            if not dst.parent.exists():
                MockFileSystemPath.trace.append(
                    f"copy({src}, {dst}) ENOENT(dst.parent)"
                )
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), str(dst)
                )
            final_dst = dst
        else:
            if dst.is_dir():
                final_dst = dst / src.name
            else:
                # Destination already exists, we're done
                MockFileSystemPath.trace.append(f"copy({src}, {dst}) noop")
                return
        final_dst.touch()
        final_dst.write_text(src.read_text())
        MockFileSystemPath.trace.append(f"copy({src}, {dst}) end")

    def move(src: Path, dst: Path):
        MockFileSystemPath.trace.append(f"move({src}, {dst}) begin")
        # A move is just a copy that unlinks the source.
        try:
            copy(src, dst)
        except Exception as exc:
            MockFileSystemPath.trace.append(f"move({src}, {dst}) copy {exc}")
            raise
        try:
            src.unlink()
        except Exception as exc:
            final_dst = dst / src.name if dst.is_dir() else dst
            try:
                final_dst.unlink(_no_special=True)
            except Exception as du_exc:
                MockFileSystemPath.trace.append(
                    f"move({src}, {dst}) unlink {exc}, dst unlink {du_exc}"
                )
            raise
        MockFileSystemPath.trace.append(f"move({src}, {dst}) end")

    def md5sum(src: str):
        src_p = MockFileSystemPath(src)
        return src_p.read_text()

    # Install the mock'd up Path
    monkeypatch.setattr(pbench.process_tb, "Path", MockFileSystemPath)
    monkeypatch.setattr(pbench.process_tb.shutil, "copy", copy)
    monkeypatch.setattr(pbench.process_tb.shutil, "move", move)
    monkeypatch.setattr(pbench.process_tb, "md5sum", md5sum)

    # This fixture yields the mock'd Path class closed over an empty instance
    # of the file system hierarchy.
    yield MockFileSystemPath


class TestMockFileSystemPath:
    @staticmethod
    def test_root_obj(file_system):
        """Verify we start with an empty "file system"."""
        assert file_system.hier == {"/": {}}

        # The fixture yields a class for creating "Path" objects, so rename it
        # to help describe what we are doing.
        MockPath = file_system

        # Verify root object
        root_p = MockPath("/")
        assert root_p.exists()
        assert root_p.is_dir()

    @staticmethod
    def test_internal_error(file_system):
        """Verify internal error handling."""
        MockPath = file_system
        err = MockPath.InternalError("foo")
        assert str(err) == "MockFileSystemPath - INTERNAL ERROR - foo"

        root_p = MockPath("/")
        root_p.parts = ("/", "wrong")
        with pytest.raises(MockPath.InternalError) as exc:
            root_p._is_root()
        assert str(exc.value).endswith("invalid root object")

        other_p = MockPath("/var/tmp")
        other_p.parts = ("/", "var", "foo")
        with pytest.raises(MockPath.InternalError) as exc:
            other_p._is_root()
        assert str(exc.value).endswith("invalid object, name does not end parts")

        path_p = MockPath("/var/log/foo")
        path_p.parent.mkdir(parents=True)
        path_p.touch()
        parent, entry = path_p._lookup_entry()
        assert entry is not None
        parent["foo"] = 15
        with pytest.raises(MockPath.InternalError) as exc:
            path_p._lookup_entry()
        assert str(exc.value).endswith("unknown object")

    @staticmethod
    def test_object_types(file_system):
        """Verify object types"""
        MockPath = file_system

        # Create a directory
        dir_p = MockPath("/var")
        assert not dir_p.exists()
        dir_p.mkdir()
        assert dir_p.is_dir() and not dir_p.is_file()
        assert not (dir_p / "tmp").is_dir()

        # Create a file
        file_p = dir_p / "file"
        assert not file_p.exists()
        file_p.touch()
        assert not file_p.is_dir() and file_p.is_file()
        assert not (dir_p / "not-a-file").is_file()

        # Create a symlink
        symlink_p = dir_p / "symlink"
        assert not symlink_p.exists()
        symlink_p.symlink_to("/var/foo")
        assert not symlink_p.is_dir() and not symlink_p.is_file()

        # Ensure files and symlinks can't be used as non-leaf path elements
        with pytest.raises(FileNotFoundError) as exc:
            (file_p / "sub-dir").mkdir()
        assert exc.value.errno == errno.ENOENT
        with pytest.raises(FileNotFoundError) as exc:
            (symlink_p / "sub-dir").mkdir()
        assert exc.value.errno == errno.ENOENT
        with pytest.raises(FileNotFoundError) as exc:
            (file_p / "file").touch()
        assert exc.value.errno == errno.ENOENT
        with pytest.raises(FileNotFoundError) as exc:
            (symlink_p / "file").touch()
        assert exc.value.errno == errno.ENOENT
        with pytest.raises(FileNotFoundError) as exc:
            (file_p / "symlink").symlink_to("/var/foo")
        assert exc.value.errno == errno.ENOENT
        with pytest.raises(FileNotFoundError) as exc:
            (symlink_p / "symlink").symlink_to("/var/foo")
        assert exc.value.errno == errno.ENOENT

        assert file_system.hier == {"/": {"var": {"file": [""], "symlink": "/var/foo"}}}

    @staticmethod
    def test_resolve(file_system):
        """Verify behavior of .resolve()"""
        MockPath = file_system

        root_p = MockPath("/")
        new_root_p = root_p.resolve()
        assert new_root_p is not root_p

        with pytest.raises(FileNotFoundError) as exc:
            MockPath("/foo").resolve(strict=True)
        assert exc.value.errno == errno.ENOENT

    @staticmethod
    def test_mkdir(file_system):
        """Verify behavior of .mkdir()"""
        MockPath = file_system

        with pytest.raises(FileExistsError) as exc:
            MockPath("/").mkdir()
        assert exc.value.errno == errno.EEXIST

        with pytest.raises(FileNotFoundError) as exc:
            MockPath("/var/tmp").mkdir()
        assert exc.value.errno == errno.ENOENT

        MockPath("/var").mkdir()
        MockPath("/var/tmp").mkdir()

        with pytest.raises(FileExistsError) as exc:
            MockPath("/var/tmp").mkdir()
        assert exc.value.errno == errno.EEXIST

        MockPath("/var/tmp").mkdir(exist_ok=True)

        MockPath("/var/tmp/this/is/long").mkdir(parents=True)

        assert file_system.hier == {
            "/": {"var": {"tmp": {"this": {"is": {"long": {}}}}}}
        }

    @staticmethod
    def test_touch(file_system):
        """Verify behavior of .touch()"""
        MockPath = file_system

        with pytest.raises(IsADirectoryError) as exc:
            MockPath("/").touch()
        assert exc.value.errno == errno.EISDIR

        MockPath("/foo").touch()

        with pytest.raises(FileNotFoundError) as exc:
            MockPath("/var/tmp/foo").touch()
        assert exc.value.errno == errno.ENOENT

        # Verify it can traverse the file system properly...
        MockPath("/var/tmp").mkdir(parents=True)
        # ... and create a file ...
        MockPath("/var/tmp/foo").touch()
        # ... and do it again without raising an error ...
        MockPath("/var/tmp/foo").touch()
        with pytest.raises(FileExistsError) as exc:
            # ... but this time raise an error.
            MockPath("/var/tmp/foo").touch(exist_ok=False)
        assert exc.value.errno == errno.EEXIST

        assert file_system.hier == {"/": {"foo": [""], "var": {"tmp": {"foo": [""]}}}}

    @staticmethod
    def test_symlink_to(file_system):
        """Verify behavior of .symlink_to()"""
        MockPath = file_system

        with pytest.raises(FileExistsError) as exc:
            MockPath("/").symlink_to("/bar")
        assert exc.value.errno == errno.EEXIST

        MockPath("/foo").symlink_to("/bar")

        with pytest.raises(FileNotFoundError) as exc:
            MockPath("/var/tmp/foo").symlink_to("/foo")
        assert exc.value.errno == errno.ENOENT

        # Verify it can traverse the file system properly...
        MockPath("/var/tmp").mkdir(parents=True)
        # ... and create a symlink.
        MockPath("/var/tmp/foo").symlink_to("bar")
        with pytest.raises(FileExistsError) as exc:
            # ... but this time raise an error.
            MockPath("/var/tmp/foo").symlink_to("mar")
        assert exc.value.errno == errno.EEXIST

        assert file_system.hier == {
            "/": {"foo": "/bar", "var": {"tmp": {"foo": "bar"}}}
        }

    @staticmethod
    def test_read_write_text(file_system):
        """Verify behaviors of .write_text() and .read_text()"""
        MockPath = file_system

        foo = MockPath("/foo")
        foo.touch()
        wtext = "this\nthat\nthen"
        foo.write_text(wtext)
        rtext = foo.read_text()
        assert rtext == wtext, f"read {rtext!r}, but expected {wtext!r}"

        wtext = "this\nthat\nthen\n"
        foo.write_text(wtext)
        rtext = foo.read_text()
        assert rtext == wtext, f"read {rtext!r}, but expected {wtext!r}"

        with pytest.raises(FileNotFoundError) as exc:
            MockPath("/bar").write_text("a")
        assert exc.value.errno == errno.ENOENT
        with pytest.raises(FileNotFoundError) as exc:
            MockPath("/bar").read_text()
        assert exc.value.errno == errno.ENOENT

        with pytest.raises(IsADirectoryError) as exc:
            MockPath("/").write_text("b")
        assert exc.value.errno == errno.EISDIR
        with pytest.raises(IsADirectoryError) as exc:
            MockPath("/").read_text()
        assert exc.value.errno == errno.EISDIR

        symlink_p = MockPath("/symlink")
        symlink_p.symlink_to("nowhere")

        with pytest.raises(OSError) as exc:
            MockPath("/symlink").write_text("b")
        assert exc.value.errno == errno.EIO
        with pytest.raises(OSError) as exc:
            MockPath("/symlink").read_text()
        assert exc.value.errno == errno.EIO

        assert file_system.hier == {
            "/": {"foo": ["this", "that", "then", ""], "symlink": "nowhere"}
        }

    @staticmethod
    def test_unlink(file_system):
        """Verify behavior of .unlink()"""
        MockPath = file_system

        with pytest.raises(IsADirectoryError) as exc:
            MockPath("/").unlink()
        assert exc.value.errno == errno.EISDIR

        dir_p = MockPath("/var")
        dir_p.mkdir()

        with pytest.raises(IsADirectoryError) as exc:
            dir_p.unlink()
        assert exc.value.errno == errno.EISDIR

        foo_p = MockPath("/var/tmp/foo")

        # Missing parent directory
        with pytest.raises(FileNotFoundError) as exc:
            foo_p.unlink()
        assert exc.value.errno == errno.ENOENT

        (dir_p / "tmp").mkdir()
        with pytest.raises(FileNotFoundError) as exc:
            # Missing file
            foo_p.unlink()
        assert exc.value.errno == errno.ENOENT

        foo_p.touch()
        assert file_system.hier == {"/": {"var": {"tmp": {"foo": [""]}}}}

        foo_p.unlink()
        assert file_system.hier == {"/": {"var": {"tmp": {}}}}

        sp1 = MockPath("/unlink_fail_tb.tar.xz")
        sp1.touch()
        sp2 = MockPath("/unlink_fail_md5.tar.xz.md5")
        sp2.touch()
        with pytest.raises(OSError) as exc:
            sp1.unlink()
        assert exc.value.errno == errno.EIO
        with pytest.raises(OSError) as exc:
            sp2.unlink()
        assert exc.value.errno == errno.EIO

    @staticmethod
    def test_glob(file_system):
        """Verify behavior of .glob()"""
        MockPath = file_system

        with pytest.raises(MockPath.InternalError) as exc:
            list(MockPath("/").glob("*"))
        assert str(exc.value).endswith("unsupported pattern '*'")

        # Create this "other" thing which should not show up anywhere.
        MockPath("/other").touch()

        # Verify ways we can't find things
        assert list(MockPath("/").glob("**/*.find")) == []
        assert list(MockPath("/does/not/exist").glob("**/*.find")) == []
        dir_p = MockPath("/does")
        dir_p.mkdir()
        exist_p = dir_p / "exist"
        exist_p.touch()
        assert list(MockPath("/does/exist").glob("**/*.find")) == []

        # Verify we can find what we created above.
        expected_list = [
            "/does",
            "/other",
            "/does/exist",
        ]
        found_list = [str(entry) for entry in MockPath("/").glob("**/*")]
        assert found_list == expected_list

        exist_p.unlink()

        # Make this directory structure.
        dir_p = MockPath("/d")
        dir_p.mkdir()
        expected_list = [
            "/d/a0",
            "/d/a1",
            "/d/b0",
            "/d/b1",
            "/d/c0",
            "/d/c1",
            "/d/c0/x0",
            "/d/c0/x1",
            "/d/b0/x0",
            "/d/b0/x1",
            "/d/b0/x0/j0",
            "/d/b0/x0/j0/k0",
            "/d/a0/x0",
            "/d/a0/x0/j0",
            "/d/a0/x0/j1",
            "/d/a0/x0/j0/k0",
        ]
        for entry in expected_list:
            MockPath(entry).mkdir(exist_ok=True)

        # Verify the linear traversal works, and does not find anything else.
        found_list = [str(entry) for entry in dir_p.glob("**/*")]
        assert found_list == expected_list

    @staticmethod
    def test_comparisons(file_system):
        """Verify behavior of __eq__() and __lt__()"""
        MockPath = file_system

        assert MockPath("/foo") == MockPath("/foo")
        assert MockPath("/foo") != MockPath("/bar")
        assert MockPath("/bar") < MockPath("/foo")
        assert MockPath("/bar") <= MockPath("/foo")
        assert MockPath("/bar") <= MockPath("/bar")
        assert MockPath("/foo") > MockPath("/bar")
        assert MockPath("/foo") >= MockPath("/bar")
        assert MockPath("/foo") >= MockPath("/foo")


def test_shutil_copy(file_system):
    """Verify behavior of the pbench.process_tb.copy mock"""
    MockPath = file_system

    orig_p = MockPath("/var/orig")
    orig_p.parent.mkdir()
    orig_p.touch()
    orig_p.write_text("abc")

    copy_p = MockPath("/var/copy")
    pbench.process_tb.shutil.copy(orig_p, copy_p)
    pbench.process_tb.shutil.copy(orig_p, copy_p)

    tmp_p = MockPath("/var/tmp")
    with pytest.raises(FileNotFoundError) as exc:
        pbench.process_tb.shutil.copy(orig_p, tmp_p / "copy")
    assert exc.value.errno == errno.ENOENT

    tmp_p.mkdir()
    pbench.process_tb.shutil.copy(orig_p, tmp_p)

    with pytest.raises(FileNotFoundError) as exc:
        pbench.process_tb.shutil.copy(tmp_p, MockPath("/"))
    assert exc.value.errno == errno.ENOENT

    assert file_system.hier == {
        "/": {"var": {"copy": ["abc"], "orig": ["abc"], "tmp": {"orig": ["abc"]}}}
    }


def test_shutil_move(file_system):
    """Verify behavior of the pbench.process_tb.move mock"""
    MockPath = file_system

    orig_p = MockPath("/var/orig")
    orig_p.parent.mkdir()
    orig_p.touch()
    orig_p.write_text("abc")

    move_p = MockPath("/var/move")
    pbench.process_tb.shutil.move(orig_p, move_p)

    with pytest.raises(FileNotFoundError) as exc:
        pbench.process_tb.shutil.move(orig_p, move_p)
    assert exc.value.errno == errno.ENOENT

    sp1 = MockPath("/unlink_fail_tb.tar.xz")
    sp1.touch()
    sp1.write_text("123")
    move_p = MockPath("/var")
    with pytest.raises(OSError) as exc:
        pbench.process_tb.shutil.move(sp1, move_p)
    assert exc.value.errno == errno.EIO

    assert file_system.hier == {
        "/": {"unlink_fail_tb.tar.xz": ["123"], "var": {"move": ["abc"]}}
    }


class MockConfig:
    TS = "run-1970-01-02T00:00:00.000000"
    ARCHIVE = "/srv/pbench/archive/fs-version-001"
    LINKDIRS = "TO-UNPACK TO-BACKUP TO-INDEX"

    def __init__(self, mappings: dict):
        self._mappings = mappings

    def get(self, section: str, option: str) -> str:
        assert (
            section in self._mappings and option in self._mappings[section]
        ), f"Unexpected configuration option, {section!r}/{option!r}, in MockConfig.get()"
        return self._mappings[section][option]


class TestProcessTb:
    """Verify all the behaviors of the "process tar balls" class"""

    version_num = "002"
    receive_dir_prefix = "/srv/pbench/pbench-move-results-receive/fs-version"
    q_dir = "/srv/pbench/quarantine"

    def test_token(self, logger):
        expected_error_msg = (
            "The 'pbench-server' section must either provide a value for"
            " the 'put-token' option, and/or the 'dispatch-states' option"
        )
        mappings = {
            "pbench-server": {
                "pbench-move-results-receive-versions": TestProcessTb.version_num,
                "pbench-receive-dir-prefix": TestProcessTb.receive_dir_prefix,
                "pbench-quarantine-dir": "",
                "put-token": "",
                "dispatch-states": "",
            }
        }
        with pytest.raises(ValueError) as e:
            ProcessTb(MockConfig(mappings), logger)

        assert expected_error_msg in str(e)

    def test_get_receive_dir_failed(self, monkeypatch, logger):
        def mock_is_dir(self: Path) -> bool:
            assert False, "Unexpected call to mocked Path.is_dir()"

        expected_error_msg = "Failed: No value for config option pbench-receive-dir-prefix in section pbench-server"
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": "",
                    "pbench-quarantine-dir": "",
                    "put-token": "Authorization-token",
                    "dispatch-states": "",
                }
            }
        )
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        with pytest.raises(ValueError) as e:
            ProcessTb(config, logger)

        assert expected_error_msg in str(e)

    def test_get_receive_dir_value_failed(self, logger, file_system):
        wrong_dir = "/srv/wrong-directory"
        expected_error_msg = f"Failed: '{wrong_dir}-{TestProcessTb.version_num}' does not exist, or is not a directory"
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": wrong_dir,
                    "pbench-quarantine-dir": "",
                    "put-token": "Authorization-token",
                    "dispatch-states": "",
                }
            }
        )
        with pytest.raises(NotADirectoryError) as e:
            ProcessTb(config, logger)

        assert expected_error_msg in str(e)
        assert file_system.hier == {"/": {}}

    @staticmethod
    def create_tar_balls(
        file_system, reception_contents: dict[str, List[str]]
    ) -> Iterator:
        MockPath = file_system
        # Create an initial reception area
        receive_path = MockPath(
            f"{TestProcessTb.receive_dir_prefix}-{TestProcessTb.version_num}"
        )
        receive_path.mkdir(parents=True)
        for ctrl, tbs in reception_contents.items():
            ctrl_d = receive_path / ctrl
            ctrl_d.mkdir()
            for tb in tbs:
                tb_f = ctrl_d / tb
                tb_f.touch()
                d = hashlib.md5()
                d.update(tb_f.name.encode("UTF-8"))
                md5val = d.hexdigest()
                tb_f.write_text(md5val)
                md5_f = ctrl_d / f"{tb}.md5"
                md5_f.touch()
                md5_f.write_text(f"{md5val} {tb_f.name}")
                yield tb_f

    def test_process_tb_put_runtime_error(
        self, monkeypatch, caplog, logger, file_system
    ):
        """Verify error handling of non-zero return code from pbench-results-push"""
        tbs = list(
            TestProcessTb.create_tar_balls(
                file_system, {"sat::ctrl": ["bad_log.tar.xz"]}
            )
        )
        exp_push_cmd = f"pbench-results-push {tbs[0]} --token=Authorization-token --metadata=server.origin:sat"

        def mock_run(*args, **kwargs) -> subprocess.CompletedProcess:
            assert args[0] == [
                "bash",
                "-l",
                "-c",
                exp_push_cmd,
            ], f"Unexpected push command, {args!r}, in mocked subprocess.run"
            assert kwargs["capture_output"] is True
            return subprocess.CompletedProcess(args, 42, stderr="forty-two")

        expected_result = Results(
            nstatus="",
            ntotal=1,
            ntbs=0,
            ndups=0,
            nqua=0,
            nerr=1,
            nserr=0,
            ncerr=0,
            nlerr=0,
        )
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": TestProcessTb.receive_dir_prefix,
                    "pbench-quarantine-dir": TestProcessTb.q_dir,
                    "put-token": "Authorization-token",
                    "dispatch-states": "",
                }
            }
        )
        expected_error_msg = "command: forty-two"
        monkeypatch.setattr(subprocess, "run", mock_run)

        res = ProcessTb(config, logger).process_tb()

        assert res == expected_result
        assert expected_error_msg in caplog.text
        assert file_system.hier["/"]["srv"]["pbench"] == {
            "pbench-move-results-receive": {
                "fs-version-002": {
                    "sat::ctrl": {
                        "bad_log.tar.xz": ["0c181c1cbe2a2353bcf977b4831ff774"],
                        "bad_log.tar.xz.md5": [
                            "0c181c1cbe2a2353bcf977b4831ff774 bad_log.tar.xz"
                        ],
                    }
                }
            },
            "quarantine": {"md5-002": {}, "duplicates-002": {}},
        }

    def test_process_tb(self, monkeypatch, logger, file_system):
        """Verify processing of tar balls without any failure"""
        MockPath = file_system
        tbs = list(
            TestProcessTb.create_tar_balls(file_system, {"ctrl": ["log.tar.xz"]})
        )
        exp_push_cmd = f"pbench-results-push {tbs[0]} --token=Authorization-token"

        def mock_run(*args, **kwargs) -> subprocess.CompletedProcess:
            assert args[0] == [
                "bash",
                "-l",
                "-c",
                exp_push_cmd,
            ], f"Unexpected push command, {args!r}, in mocked subprocess.run"
            assert kwargs["capture_output"] is True
            return subprocess.CompletedProcess(args, 0)

        expected_result = Results(
            nstatus=f": processed {tbs[0].name}\n",
            ntotal=1,
            ntbs=1,
            ndups=0,
            nqua=0,
            nerr=0,
            nserr=0,
            ncerr=0,
            nlerr=0,
        )
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": TestProcessTb.receive_dir_prefix,
                    "pbench-quarantine-dir": TestProcessTb.q_dir,
                    "put-token": "Authorization-token",
                    "dispatch-states": "",
                }
            }
        )
        monkeypatch.setattr(subprocess, "run", mock_run)

        res = ProcessTb(config, logger).process_tb()

        assert res == expected_result
        assert MockPath.hier["/"]["srv"]["pbench"] == {
            "pbench-move-results-receive": {"fs-version-002": {"ctrl": {}}},
            "quarantine": {"md5-002": {}, "duplicates-002": {}},
        }

    def test_process_tb_zero(self, monkeypatch, logger, file_system):
        """verify processing if there are no TBs without any failure"""
        MockPath = file_system
        # Create an initial reception area
        receive_path = MockPath(
            f"{TestProcessTb.receive_dir_prefix}-{TestProcessTb.version_num}"
        )
        receive_path.mkdir(parents=True)

        def mock_results_push(tb: Path, token: str, sat_prefix: str) -> None:
            assert False, "Unexpected call to mocked result_push function"

        expected_result = Results(
            nstatus="",
            ntotal=0,
            ntbs=0,
            ndups=0,
            nqua=0,
            nerr=0,
            nserr=0,
            ncerr=0,
            nlerr=0,
        )
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": TestProcessTb.receive_dir_prefix,
                    "pbench-quarantine-dir": TestProcessTb.q_dir,
                    "put-token": "Authorization-token",
                    "dispatch-states": "",
                }
            }
        )
        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)

        res = ProcessTb(config, logger).process_tb()

        assert res == expected_result
        assert MockPath.hier["/"]["srv"]["pbench"] == {
            "pbench-move-results-receive": {"fs-version-002": {}},
            "quarantine": {"md5-002": {}, "duplicates-002": {}},
        }

    def test_multiple_process_tb_put_only(
        self, monkeypatch, caplog, logger, file_system
    ):
        """Verify tar ball processing via the PUT API at the time of failure as
        well as success"""
        MockPath = file_system
        unlink_fail_md5_name = "unlink_fail_md5.tar.xz"
        unlink_fail_tb_name = "unlink_fail_tb.tar.xz"
        tbs = list(
            TestProcessTb.create_tar_balls(
                file_system,
                {
                    "good-and-bad": ["log.tar.xz", "bad_log.tar.xz"],
                    "unlink-fails": [unlink_fail_tb_name, unlink_fail_md5_name],
                },
            )
        )
        bad_tb = tbs[1]

        def mock_results_push(tb: MockPath, token: str, sat_prefix: str) -> None:
            if tb.name.startswith("bad_"):
                raise RuntimeError(f"No such file or directory: '{tb}'")
            return

        expected_result = Results(
            nstatus=f": processed log.tar.xz\n: processed {unlink_fail_md5_name}\n: processed {unlink_fail_tb_name}\n",
            ntotal=4,
            ntbs=3,
            ndups=0,
            nqua=0,
            nerr=1,
            nserr=0,
            ncerr=2,
            nlerr=0,
        )
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": TestProcessTb.receive_dir_prefix,
                    "pbench-quarantine-dir": TestProcessTb.q_dir,
                    "put-token": "Authorization-token",
                    "dispatch-states": "",
                }
            }
        )
        expected_error_msg = f"No such file or directory: '{bad_tb}'"
        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)
        caplog.set_level(logging.ERROR, logger=logger.name)

        res = ProcessTb(config, logger).process_tb()

        assert res == expected_result
        assert expected_error_msg in caplog.text
        assert unlink_fail_md5_name in caplog.text
        assert unlink_fail_tb_name in caplog.text
        assert MockPath.hier["/"]["srv"]["pbench"] == {
            "pbench-move-results-receive": {
                "fs-version-002": {
                    "good-and-bad": {
                        "bad_log.tar.xz": ["0c181c1cbe2a2353bcf977b4831ff774"],
                        "bad_log.tar.xz.md5": [
                            "0c181c1cbe2a2353bcf977b4831ff774 bad_log.tar.xz"
                        ],
                    },
                    "unlink-fails": {
                        "unlink_fail_tb.tar.xz": ["ddb5bdceeb201f8f94a5e6083089f8c3"],
                        "unlink_fail_md5.tar.xz.md5": [
                            "0a0b35f6ca2f9f2055c1f37ad3bbea60 unlink_fail_md5.tar.xz"
                        ],
                    },
                }
            },
            "quarantine": {"md5-002": {}, "duplicates-002": {}},
        }

    def test_multiple_process_tb_dispatch_only(
        self, monkeypatch, caplog, logger, file_system
    ):
        """Verify tar ball processing of legacy SSH at the time of failure as
        well as success"""
        MockPath = file_system
        unlink_fail_md5_name = "unlink_fail_md5.tar.xz"
        unlink_fail_tb_name = "unlink_fail_tb.tar.xz"
        tbs = list(
            TestProcessTb.create_tar_balls(
                file_system,
                {
                    "good-and-bad": ["log.tar.xz", "bad_log.tar.xz"],
                    "unlink-fails": [unlink_fail_tb_name, unlink_fail_md5_name],
                },
            )
        )
        # The 3rd tar ball won't be moved.
        unlink_tb = tbs[2]
        unlink_md5 = tbs[3]

        def mock_results_push(tb: MockPath, token: str, sat_prefix: str) -> None:
            assert False, "_results_push() unexpectedly called"

        expected_result = Results(
            nstatus=f": processed bad_log.tar.xz\n: processed log.tar.xz\n: processed {unlink_fail_md5_name}\n",
            ntotal=4,
            ntbs=3,
            ndups=0,
            nqua=0,
            nerr=1,
            nserr=0,
            ncerr=0,
            nlerr=0,
        )
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": TestProcessTb.receive_dir_prefix,
                    "pbench-quarantine-dir": TestProcessTb.q_dir,
                    "put-token": "",
                    "dispatch-states": "TO-UNPACK TO-BACKUP",
                }
            }
        )
        MockPath(config.ARCHIVE).mkdir(parents=True)
        restorecon_cmds = []

        def mock_run(*args, **kwargs) -> subprocess.CompletedProcess:
            assert args[0][:-1] == [
                "bash",
                "-l",
                "-c",
            ], f"Unexpected restorecon command prefix, {args!r}, in mocked subprocess.run"
            restorecon_cmds.append(args[0][-1])
            assert kwargs["capture_output"] is True
            return subprocess.CompletedProcess(args, 0)

        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)
        monkeypatch.setattr(subprocess, "run", mock_run)
        caplog.set_level(logging.ERROR, logger=logger.name)

        res = ProcessTb(config, logger).process_tb()

        assert (
            res == expected_result
        ), f"res={res}, fs-hier:{file_system.hier}, trace={file_system.trace}"
        gb_ctrl = f"{config.ARCHIVE}/good-and-bad/"
        uf_ctrl = f"{config.ARCHIVE}/unlink-fails/"
        assert restorecon_cmds == [
            f"restorecon {gb_ctrl}bad_log.tar.xz {gb_ctrl}bad_log.tar.xz.md5",
            f"restorecon {gb_ctrl}log.tar.xz {gb_ctrl}log.tar.xz.md5",
            f"restorecon {uf_ctrl}{unlink_fail_md5_name} {uf_ctrl}{unlink_fail_md5_name}.md5",
        ]
        assert (
            f"in cleanup of successful copy, removal of file '{unlink_md5}.md5'"
            in caplog.text
        ), f"{unlink_md5} {caplog.text}"
        assert (
            f"move to archive for tar ball '{unlink_tb}'" in caplog.text
        ), f"{unlink_tb} {caplog.text}"
        assert file_system.hier["/"]["srv"]["pbench"] == {
            "pbench-move-results-receive": {
                "fs-version-002": {
                    "good-and-bad": {},
                    "unlink-fails": {
                        "unlink_fail_tb.tar.xz": ["ddb5bdceeb201f8f94a5e6083089f8c3"],
                        "unlink_fail_tb.tar.xz.md5": [
                            "ddb5bdceeb201f8f94a5e6083089f8c3 unlink_fail_tb.tar.xz"
                        ],
                        "unlink_fail_md5.tar.xz.md5": [
                            "0a0b35f6ca2f9f2055c1f37ad3bbea60 unlink_fail_md5.tar.xz"
                        ],
                    },
                }
            },
            "archive": {
                "fs-version-001": {
                    "good-and-bad": {
                        "TO-UNPACK": {
                            "bad_log.tar.xz": f"{gb_ctrl}bad_log.tar.xz",
                            "log.tar.xz": f"{gb_ctrl}log.tar.xz",
                        },
                        "TO-BACKUP": {
                            "bad_log.tar.xz": f"{gb_ctrl}bad_log.tar.xz",
                            "log.tar.xz": f"{gb_ctrl}log.tar.xz",
                        },
                        "TO-INDEX": {},
                        "bad_log.tar.xz.md5": [
                            "0c181c1cbe2a2353bcf977b4831ff774 bad_log.tar.xz"
                        ],
                        "bad_log.tar.xz": ["0c181c1cbe2a2353bcf977b4831ff774"],
                        "log.tar.xz.md5": [
                            "460439ec9fe44288ca8de5721ea336c6 log.tar.xz"
                        ],
                        "log.tar.xz": ["460439ec9fe44288ca8de5721ea336c6"],
                    },
                    "unlink-fails": {
                        "TO-UNPACK": {
                            "unlink_fail_md5.tar.xz": f"{uf_ctrl}unlink_fail_md5.tar.xz"
                        },
                        "TO-BACKUP": {
                            "unlink_fail_md5.tar.xz": f"{uf_ctrl}unlink_fail_md5.tar.xz"
                        },
                        "TO-INDEX": {},
                        "unlink_fail_md5.tar.xz.md5": [
                            "0a0b35f6ca2f9f2055c1f37ad3bbea60 unlink_fail_md5.tar.xz"
                        ],
                        "unlink_fail_md5.tar.xz": ["0a0b35f6ca2f9f2055c1f37ad3bbea60"],
                    },
                }
            },
            "quarantine": {"md5-002": {}, "duplicates-002": {}},
        }

    def test_multiple_process_tb_put_and_dispatch(
        self, monkeypatch, logger, file_system
    ):
        """Verify tar ball processing of legacy SSH and PUT API"""
        MockPath = file_system
        list(
            TestProcessTb.create_tar_balls(
                file_system,
                {
                    "good": ["log.tar.xz"],
                },
            )
        )

        def mock_results_push(tb: MockPath, token: str, sat_prefix: str) -> None:
            assert False, "_results_push() unexpectedly called"

        expected_result = Results(
            nstatus=": processed log.tar.xz\n",
            ntotal=1,
            ntbs=1,
            ndups=0,
            nqua=0,
            nerr=0,
            nserr=0,
            ncerr=0,
            nlerr=0,
        )
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": TestProcessTb.receive_dir_prefix,
                    "pbench-quarantine-dir": TestProcessTb.q_dir,
                    "put-token": "Authorization-token",
                    "dispatch-states": "TO-UNPACK TO-BACKUP",
                }
            }
        )
        MockPath(config.ARCHIVE).mkdir(parents=True)
        restorecon_cmds = []

        def mock_run(*args, **kwargs) -> subprocess.CompletedProcess:
            assert args[0][:-1] == [
                "bash",
                "-l",
                "-c",
            ], f"Unexpected restorecon command prefix, {args!r}, in mocked subprocess.run"
            restorecon_cmds.append(args[0][-1])
            assert kwargs["capture_output"] is True
            return subprocess.CompletedProcess(args, 0)

        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)
        monkeypatch.setattr(subprocess, "run", mock_run)

        res = ProcessTb(config, logger).process_tb()

        assert (
            res == expected_result
        ), f"res={res}, fs-hier:{file_system.hier}, trace={file_system.trace}"
        good_ctrl = f"{config.ARCHIVE}/good/"
        assert restorecon_cmds == [
            f"restorecon {good_ctrl}log.tar.xz {good_ctrl}log.tar.xz.md5",
        ]
        assert file_system.hier["/"]["srv"]["pbench"] == {
            "pbench-move-results-receive": {"fs-version-002": {"good": {}}},
            "archive": {
                "fs-version-001": {
                    "good": {
                        "TO-UNPACK": {
                            "log.tar.xz": f"{good_ctrl}log.tar.xz",
                        },
                        "TO-BACKUP": {
                            "log.tar.xz": f"{good_ctrl}log.tar.xz",
                        },
                        "TO-INDEX": {},
                        "log.tar.xz.md5": [
                            "460439ec9fe44288ca8de5721ea336c6 log.tar.xz"
                        ],
                        "log.tar.xz": ["460439ec9fe44288ca8de5721ea336c6"],
                    }
                }
            },
            "quarantine": {"md5-002": {}, "duplicates-002": {}},
        }

    def test_multiple_process_dispatch_only_duplicate(
        self, monkeypatch, logger, file_system
    ):
        """Verify tar ball processing of legacy SSH duplicate handling"""
        MockPath = file_system
        list(
            TestProcessTb.create_tar_balls(
                file_system,
                {
                    "good": ["log.tar.xz", "bog.tar.xz"],
                },
            )
        )

        expected_result = Results(
            nstatus="",
            ntotal=2,
            ntbs=0,
            ndups=2,
            nqua=0,
            nerr=0,
            nserr=0,
            ncerr=0,
            nlerr=0,
        )
        config = MockConfig(
            {
                "pbench-server": {
                    "pbench-move-results-receive-versions": TestProcessTb.version_num,
                    "pbench-receive-dir-prefix": TestProcessTb.receive_dir_prefix,
                    "pbench-quarantine-dir": TestProcessTb.q_dir,
                    "put-token": "",
                    "dispatch-states": "TO-UNPACK TO-BACKUP",
                }
            }
        )
        good_ctrl = MockPath(f"{config.ARCHIVE}/good")
        good_ctrl.mkdir(parents=True)
        # Force the duplicate handling case, one for the tar ball one for the
        # .md5 file being duplicate.
        (good_ctrl / "log.tar.xz").touch()
        (good_ctrl / "bog.tar.xz.md5").touch()

        res = ProcessTb(config, logger).process_tb()

        assert (
            res == expected_result
        ), f"res={res}, fs-hier:{file_system.hier}, trace={file_system.trace}"
        assert file_system.hier["/"]["srv"]["pbench"] == {
            "pbench-move-results-receive": {"fs-version-002": {"good": {}}},
            "archive": {
                "fs-version-001": {"good": {"log.tar.xz": [""], "bog.tar.xz.md5": [""]}}
            },
            "quarantine": {
                "md5-002": {},
                "duplicates-002": {
                    "good": {
                        "bog.tar.xz": ["a1f24c23a4287861c5c32ecec6d905f3"],
                        "bog.tar.xz.md5": [
                            "a1f24c23a4287861c5c32ecec6d905f3 bog.tar.xz"
                        ],
                        "log.tar.xz": ["460439ec9fe44288ca8de5721ea336c6"],
                        "log.tar.xz.md5": [
                            "460439ec9fe44288ca8de5721ea336c6 log.tar.xz"
                        ],
                    }
                },
            },
        }
