from pathlib import Path
from typing import Iterable, Optional

import pytest

from pbench.agent.tool_group import BadToolGroup, ToolGroup


class Test_VerifyToolGroup:
    """The class data members and the `mock_resolve()` method together
    facilitate a mocked file system structure as follows:

        /mock
            /pbench_run -> pbench-agent
            /pbench-agent
                <tool group prefix>-tool-group

    The mock_resolve() method below is intended to provide "resolve" the fake
    symlink, "pbench_run" and return a fully resolved Path.
    """

    pbench_run = "/mock/pbench_run"
    pbench_agent = "pbench-agent"
    group = "tool-group"
    mock_tg_dir_name = f"{pbench_run}/{ToolGroup.TOOL_GROUP_PREFIX}-{group}"

    @staticmethod
    def mock_resolve(path: Path, strict: Optional[bool] = False) -> Path:
        """Return a "resolved" Path object.

        Args:
            strict: Not used in the mock

        Returns:
            new Path with fake resolution
        """
        assert strict, "'strict' is unexpectedly false"
        if path.parent.name == "pbench_run":
            return path.parent.parent / "pbench-agent" / path.name
        return path

    @staticmethod
    def mock_resolve_fnf(path: Path, strict: Optional[bool] = False) -> Path:
        assert strict, "'strict' is unexpectedly false"
        raise FileNotFoundError(f"Mock Path('{path.name}').resolve()")

    def test_pbench_run_value(self, monkeypatch):
        """Check behaviour when the pbench run value does not exist"""

        monkeypatch.delenv("pbench_run", False)
        expected_error_msg = f"Cannot validate tool group, '{self.group}', 'pbench_run' environment variable missing"
        with pytest.raises(BadToolGroup) as exc:
            ToolGroup.verify_tool_group(self.group)
        assert expected_error_msg in str(exc)

    def test_pbench_run_empty_value(self):
        """Check behaviour when the pbench run value is an empty string"""

        expected_error_msg = f"Cannot validate tool group, '{self.group}', 'pbench_run' environment variable missing"
        with pytest.raises(BadToolGroup) as exc:
            ToolGroup.verify_tool_group(self.group, "")
        assert expected_error_msg in str(exc)

    def test_pbench_run_dir_exist(self, monkeypatch):
        """Verify behaviour when pbench_run directory exist"""

        expected_error_msg = f"Bad tool group, '{self.group}': directory {self.mock_tg_dir_name} does not exist"
        monkeypatch.setattr(Path, "resolve", self.mock_resolve_fnf)
        with pytest.raises(BadToolGroup) as exc:
            ToolGroup.verify_tool_group(self.group, self.pbench_run)
        assert expected_error_msg in str(exc)

    def test_target_dir_exist(self, monkeypatch):
        """Test target directory exist with pbench run value as environment value"""

        pbench_run = "/mock/environ_val/pbench_run"
        monkeypatch.setenv("pbench_run", pbench_run)
        monkeypatch.setattr(Path, "resolve", self.mock_resolve_fnf)
        mock_tg_dir_name = f"{pbench_run}/{ToolGroup.TOOL_GROUP_PREFIX}-{self.group}"
        expected_error_msg = f"Bad tool group, '{self.group}': directory {mock_tg_dir_name} does not exist"
        with pytest.raises(BadToolGroup) as exc:
            ToolGroup.verify_tool_group(self.group)
        assert expected_error_msg in str(exc)

    def test_target_dir_exception(self, monkeypatch):
        """Verify Target Directory Path"""

        def mock_resolve(path: Path, strict: Optional[bool] = False) -> Path:
            """Mock Path.resolve() to raise an error while resolving"""
            assert strict, "'strict' is unexpectedly false"
            raise AttributeError(f"Mock Path('{path.name}').resolve()")

        expected_error_msg = f"Bad tool group, '{self.group}': error resolving {self.mock_tg_dir_name} directory"
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        with pytest.raises(BadToolGroup) as exc:
            ToolGroup.verify_tool_group(self.group, self.pbench_run)
        assert expected_error_msg in str(exc)

    def test_target_dir_is_directory(self, monkeypatch):
        """Test verify_tool_group() when the target directory is not a directory."""

        expected_error_msg = f"Bad tool group, '{self.group}': directory {self.mock_tg_dir_name} not valid"
        monkeypatch.setattr(Path, "resolve", self.mock_resolve)
        monkeypatch.setattr(Path, "is_dir", lambda self: False)
        with pytest.raises(BadToolGroup) as exc:
            ToolGroup.verify_tool_group(self.group, self.pbench_run)
        assert expected_error_msg in str(exc)

    def test_target_dir(self, monkeypatch):
        """Test the verify_tool_group() normal operation"""

        monkeypatch.setattr(Path, "resolve", self.mock_resolve)
        monkeypatch.setattr(Path, "is_dir", lambda self: True)
        tg_dir = ToolGroup.verify_tool_group(self.group, self.pbench_run)
        assert tg_dir.name == f"{ToolGroup.TOOL_GROUP_PREFIX}-{self.group}"
        assert tg_dir.parent.name == self.pbench_agent


class Test_ToolGroup:
    """Verify ToolGroup class"""

    @staticmethod
    def mock_verify_tool_group(name: str, pbench_run: Optional[str] = None) -> Path:
        return Path("/mock/pbench-agent")

    @staticmethod
    def mock_is_dir(path: Path) -> bool:
        """Mocked directory check"""
        return True

    @staticmethod
    def mock_read_text_fnf(path: Path) -> str:
        """Mocked read text, file not found"""
        raise FileNotFoundError(f"Mock Path('{path.name}').read_text()")

    def test_target_trigger_file(self, monkeypatch):
        """Verify if the trigger file exists"""

        monkeypatch.setattr(
            ToolGroup, "verify_tool_group", staticmethod(self.mock_verify_tool_group)
        )
        monkeypatch.setattr(Path, "iterdir", lambda path: [])
        monkeypatch.setattr(Path, "is_dir", self.mock_is_dir)
        monkeypatch.setattr(Path, "read_text", self.mock_read_text_fnf)
        tg = ToolGroup("wrong-file")
        assert tg.trigger is None

    def test_target_trigger_empty_file(self, monkeypatch):
        """Verify the trigger file is empty"""
        monkeypatch.setattr(
            ToolGroup, "verify_tool_group", staticmethod(self.mock_verify_tool_group)
        )
        monkeypatch.setattr(Path, "iterdir", lambda path: [])
        monkeypatch.setattr(Path, "is_dir", self.mock_is_dir)
        monkeypatch.setattr(Path, "read_text", lambda path: "")
        tg = ToolGroup("tool-group")
        assert tg.trigger is None

    def test_target_trigger_file_contents(self, monkeypatch):
        """Verify the contents of the Trigger file"""
        trigger_file_content = "trigger_file_contents"

        def mock_read_text(path: Path) -> str:
            """Mocked read file check, returns contents"""
            return trigger_file_content

        monkeypatch.setattr(
            ToolGroup, "verify_tool_group", staticmethod(self.mock_verify_tool_group)
        )
        monkeypatch.setattr(Path, "iterdir", lambda path: [])
        monkeypatch.setattr(Path, "is_dir", self.mock_is_dir)
        monkeypatch.setattr(Path, "read_text", mock_read_text)
        tg = ToolGroup("tool-group")
        assert tg.trigger is trigger_file_content

    def test_tool_group_empty_dir(self, monkeypatch):
        """Verify empty tool group Directory"""

        def mock_is_dir(path: Path) -> bool:
            raise AssertionError(f"Unexpected call to Path('{path.name}').is_dir()")

        monkeypatch.setattr(
            ToolGroup, "verify_tool_group", staticmethod(self.mock_verify_tool_group)
        )
        monkeypatch.setattr(Path, "iterdir", lambda path: [])
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "read_text", self.mock_read_text_fnf)
        tg = ToolGroup("tool-group")
        assert tg.trigger is None
        assert tg.name == "tool-group"
        assert tg.get_label("hostname") == ""
        assert tg.get_tools("hostname") == {}

    class MockPath:
        """A special Path mock which provides an in-memory representation of
        an fictional on-disk structure for verifying the behavior of a
        ToolGroup object, and used for generating a list of tool group
        directory names.

        The "on-disk" hierarchy looks as follows ("/mock" prefix should not be
        encountered):

            /mock/
                pbench-agent/
                    # A "run" directory used to verify the ToolGroup
                    # constructor and methods.
                    <prefix>-mytools/
                        __trigger__
                        host1/
                            tool2
                            tool3
                            tool3.__noinstall__@
                        host2/
                            __label__
                            tool1
                        host3/
                            __label__
                            tool1
                            tool2
                            tool3
                            tool3.__noinstall__@
                    # A file that should be ignored.
                    ignore_me_file
                    # A directory that should be ignored.
                    ignore_me_dir
                pbench-agent-ntgd/
                    # A "run" directory used to verify the ToolGroup class's
                    # gen_tool_groups() class method, where no tool groups are
                    # present (simple empty directory).
                pbench-agent-multi/
                    # A "run" directory used to also verify the ToolGroup
                    # class's gen_tool_groups() class method where multiple
                    # tool groups are available (they are empty so that the
                    # ToolGroup constructor is a no-op).
                    <prefix>-heavy/
                    <prefix>-light/
                    <prefix>-medium/

        Any field (class or object) or method of the class that is used for
        the operation of the tests is given a leading underscore ("_").

        The tests all start by providing a particular "pbench run" directory
        so that all other generated file system objects are also MockPath
        class objects.

        """

        # The "known" path names to determine behavior.
        _RD_ONE_TOOL_GROUP = "pbench-agent"
        _RD_NO_TOOL_GROUPS = f"{_RD_ONE_TOOL_GROUP}-ntgd"
        _RD_MULTI_TOOL_GROUPS = f"{_RD_ONE_TOOL_GROUP}-multi"

        # Tool group names that will be found by the `.glob()` method for
        # TOOL_GROUP_MULTI.
        _tool_group_names = {"heavy", "light", "medium"}

        # Single tool group name for constructor behavior.
        _single_tg = "mytools"

        # Set of all file names
        _files = {
            "__trigger__",
            "__label__",
            "tool1",
            "tool2",
            "tool3",
            "ignore_me_file",
        }

        # Set of all symlink names
        _symlinks = {"tool3.__noinstall__"}

        # Set of all directories, used as a prefix to avoid repeats
        _dirs = {
            "mock",
            _RD_ONE_TOOL_GROUP,
            "host",
            ToolGroup.TOOL_GROUP_PREFIX,
            "ignore_me_dir",
        }

        # Expected trigger file contents
        _trigger_contents = "trigger file contents"

        # Templates for creating file content for label and tool files
        _label_template = "{} label file contents"
        _opt_template = "tool opts for {}/{}"

        _directories = {
            _RD_ONE_TOOL_GROUP: {
                f"{ToolGroup.TOOL_GROUP_PREFIX}-{_single_tg}",
                "ignore_me_dir",
                "ignore_me_file",
            },
            _RD_NO_TOOL_GROUPS: set(),
            _RD_MULTI_TOOL_GROUPS: {
                f"{ToolGroup.TOOL_GROUP_PREFIX}-{n}" for n in _tool_group_names
            },
            f"{ToolGroup.TOOL_GROUP_PREFIX}-{_single_tg}": {
                "__trigger__",
                "host1",
                "host2",
                "host3",
            },
            "host1": {"tool2", "tool3", "tool3.__noinstall__"},
            "host2": {"__label__", "tool1"},
            "host3": {"__label__", "tool1", "tool2", "tool3", "tool3.__noinstall__"},
        }

        def __init__(self, name: str, subdir: Optional[str] = None):
            # Use `Path` to get name and parent.
            p = Path(name)
            if subdir:
                p = p / subdir
            self.parts = p.parts
            self.name = p.name
            if p.parent is p:
                self.parent = self
            else:
                self.parent = Test_ToolGroup.MockPath(str(p.parent))

        def __str__(self):
            if self.parent is self:
                return self.name
            parent = str(self.parent)
            parent = "" if parent == "/" else parent
            return f"{parent}/{self.name}"

        def __repr__(self):
            return f"MockPath(name={self.name!r}, parent='{self.parent}', parts={self.parts!r})"

        def glob(self, prefix: str) -> Iterable[Path]:
            """Mock'd glob which always returns MockPath objects from the set
            of `_names`, unless the name of the object is special.
            """
            if self.name == self._RD_NO_TOOL_GROUPS:
                # The special name which for a directory which "does not
                # have tool groups".
                return
            if self.name == self._RD_MULTI_TOOL_GROUPS:
                for n in self._tool_group_names:
                    # Return the 3 tools groups that are found with the prefix
                    # attached, stripping the `*` and replacing it with the
                    # value of `n`.
                    yield Test_ToolGroup.MockPath(str(self), f"{prefix[:-1]}{n}")
                return
            if self.name == self._RD_ONE_TOOL_GROUP:
                yield Test_ToolGroup.MockPath(str(self), "ignore_me_file")
                yield Test_ToolGroup.MockPath(
                    str(self), f"{prefix[:-1]}{self._single_tg}"
                )
                yield Test_ToolGroup.MockPath(str(self), "ignore_me_dir")
                return
            raise AssertionError(f"MockPath('{self}').glob() unexpectedly called")

        def resolve(self, strict: Optional[bool] = False) -> Path:
            """No-op for resolve() which just returns another MockPath object."""
            assert strict, f"MockPath('{self}').resolve(strict=False)"
            return self

        def is_dir(self) -> bool:
            """Lookup directory names."""
            for d in self._dirs:
                if self.name.startswith(d):
                    return True
            return False

        def read_text(self) -> str:
            """Provides fake file contents, raises file-not-found exceptions,
            and assertion errors for unexpected behaviors.
            """
            if self.is_dir():
                raise AssertionError(f"Unexpected MockPath('{self}').read_text()")
            if self.name not in self._files:
                raise FileNotFoundError(self.name)
            if self.name == "__trigger__":
                return self._trigger_contents
            if self.name == "__label__":
                assert self.parent, f"{self!r}"
                return self._label_template.format(self.parent.name)
            if self.name[:-1] == "tool":
                assert self.parent, f"{self!r}"
                return self._opt_template.format(self.parent.name, self.name)
            raise AssertionError(f"Unexpected MockPath('{self}').read_text()")

        def __truediv__(self, arg: str) -> Path:
            return Test_ToolGroup.MockPath(str(self), arg)

        def iterdir(self) -> Iterable[Path]:
            """Return what we have "on-disk"."""
            if not self.is_dir():
                raise AssertionError(f"Unexpected MockPath('{self}').iterdir()")
            dir_set = self._directories.get(self.name, set())
            for dirent in dir_set:
                yield Test_ToolGroup.MockPath(str(self), dirent)

    def test_tool_group_dir(self, monkeypatch):
        """Verify ToolGroup class normal operation"""

        expected_tools = {
            "host1": {
                "tool2": self.MockPath._opt_template.format("host1", "tool2"),
                "tool3": self.MockPath._opt_template.format("host1", "tool3"),
            },
            "host2": {
                "tool1": self.MockPath._opt_template.format("host2", "tool1"),
            },
            "host3": {
                "tool1": self.MockPath._opt_template.format("host3", "tool1"),
                "tool2": self.MockPath._opt_template.format("host3", "tool2"),
                "tool3": self.MockPath._opt_template.format("host3", "tool3"),
            },
        }
        expected_labels = {
            "host1": "",
            "host2": self.MockPath._label_template.format("host2"),
            "host3": self.MockPath._label_template.format("host3"),
        }
        expected_hostnames = {
            "host1": {
                "tool2": "tool opts for host1/tool2",
                "tool3": "tool opts for host1/tool3",
            },
            "host2": {"tool1": "tool opts for host2/tool1"},
            "host3": {
                "tool1": "tool opts for host3/tool1",
                "tool2": "tool opts for host3/tool2",
                "tool3": "tool opts for host3/tool3",
            },
        }

        monkeypatch.setenv("pbench_run", f"/mock/{self.MockPath._RD_ONE_TOOL_GROUP}")
        monkeypatch.setattr("pbench.agent.tool_group.Path", self.MockPath)
        tg = ToolGroup(self.MockPath._single_tg)
        assert tg.name == self.MockPath._single_tg
        assert tg.trigger == self.MockPath._trigger_contents
        assert tg.hostnames == expected_hostnames
        for host in expected_hostnames.keys():
            assert tg.get_tools(host) == expected_tools[host]
            assert tg.get_label(host) == expected_labels[host]
        assert tg.get_tools("bad-host") == {}
        assert tg.get_label("bad-host") == ""

    def test_gen_tool_groups(self, monkeypatch):
        """Verify the tool group directory generator."""

        monkeypatch.setattr("pbench.agent.tool_group.Path", self.MockPath)

        # To verify the case where there are no tool groups created, we make
        # a special Path object which will expose no tool groups.
        tgs = list(
            ToolGroup.gen_tool_groups(f"/mock/{self.MockPath._RD_NO_TOOL_GROUPS}")
        )
        assert len(tgs) == 0

        # Using a Path object which does have tool groups, we verify that
        # the expected generated list of Tool Group objects matches the list
        # of names we expect.
        names = {
            tg.name
            for tg in ToolGroup.gen_tool_groups(
                f"/mock/{self.MockPath._RD_MULTI_TOOL_GROUPS}"
            )
        }
        assert names == self.MockPath._tool_group_names
