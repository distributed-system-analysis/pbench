import os
from pathlib import Path

import pytest

from pbench.agent.tool_group import BadToolGroup, ToolGroup


class Test_VerifyToolGroup:

    pbench_run = "/mock/pbench_run"
    group = "tool-group"
    mock_tg_dir_name = Path(pbench_run, f"{ToolGroup.TOOL_GROUP_PREFIX}-{group}")
    tool_group_dir = Path("/mock/pbench-agent")

    def mock_resolve(self: Path, strict: bool = False):
        """
        Return a "full" fake file name

        Args:
            strict: Not used in the mock

        Returns:
            new Path with fake resolution
        """
        return self.tool_group_dir

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

        def mock_resolve(path: Path, strict: bool):
            assert strict, "'strict' is unexpectedly false"
            raise FileNotFoundError("Mock Path.resolve()")

        expected_error_msg = f"Bad tool group, '{self.group}': directory {self.mock_tg_dir_name} does not exist"
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        with pytest.raises(BadToolGroup) as exc:
            ToolGroup.verify_tool_group(self.group, self.pbench_run)
        assert expected_error_msg in str(exc)

    def test_target_dir_exist(self, monkeypatch):
        """Test target directory exist with pbench run value as environment value"""

        def mock_resolve(path: Path, strict: bool):
            assert strict, "'strict' is unexpectedly false"
            raise FileNotFoundError("Mock Path.resolve()")

        pbench_run = "/mock/environ_val/pbench_run"
        monkeypatch.setenv("pbench_run", pbench_run)
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        mock_tg_dir_name = Path(
            pbench_run, f"{ToolGroup.TOOL_GROUP_PREFIX}-{self.group}"
        )
        expected_error_msg = f"Bad tool group, '{self.group}': directory {mock_tg_dir_name} does not exist"
        with pytest.raises(BadToolGroup) as exc:
            ToolGroup.verify_tool_group(self.group)
        assert expected_error_msg in str(exc)

    def test_target_dir_exception(self, monkeypatch):
        """Verify Target Directory Path"""

        def mock_resolve(self, strict=True):
            """Mocked the check to see if the path exists"""
            assert strict, "'strict' is unexpectedly false"
            raise AttributeError("Mock Path.resolve()")

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
        assert tg_dir == self.tool_group_dir


class Test_ToolGroup:
    """Verify ToolGroup class"""

    def mock_verify_tool_group(name: str, pbench_run: Path):
        return Path("/mock/pbench-agent")

    def mock_is_dir(self: Path):
        """Mocked directory check"""
        return True

    def test_target_trigger_file(self, monkeypatch):
        """Verify if the trigger file exists"""

        def mock_read_text(self: Path):
            """Mocked directory check"""
            raise FileNotFoundError("Mock Path.resolve()")

        monkeypatch.setattr(ToolGroup, "verify_tool_group", self.mock_verify_tool_group)
        monkeypatch.setattr(os, "listdir", lambda path: [])
        monkeypatch.setattr(Path, "is_dir", self.mock_is_dir)
        monkeypatch.setattr(Path, "read_text", mock_read_text)
        tg = ToolGroup("wrong-file")
        assert tg.trigger is None

    def test_target_trigger_empty_file(self, monkeypatch):
        """verify if the trigger file is empty"""
        monkeypatch.setattr(ToolGroup, "verify_tool_group", self.mock_verify_tool_group)
        monkeypatch.setattr(os, "listdir", lambda path: [])
        monkeypatch.setattr(Path, "is_dir", self.mock_is_dir)
        monkeypatch.setattr(Path, "read_text", lambda path: "")
        tg = ToolGroup("tool-group")
        assert tg.trigger is None

    def test_target_trigger_file_contents(self, monkeypatch):
        """Verify the contesnts of the Trigger file"""
        trigger_file_content = "trigger_file_contents"

        def mock_read_text(self: Path):
            """Mocked read file check"""
            return trigger_file_content

        monkeypatch.setattr(ToolGroup, "verify_tool_group", self.mock_verify_tool_group)
        monkeypatch.setattr(os, "listdir", lambda path: [])
        monkeypatch.setattr(Path, "is_dir", self.mock_is_dir)
        monkeypatch.setattr(Path, "read_text", mock_read_text)
        tg = ToolGroup("tool-group")
        assert tg.trigger is trigger_file_content

    def test_tool_group_empty_dir(self, monkeypatch):
        """Verify empty tool group Directory"""

        def mock_is_dir(self):
            raise AssertionError("Unexpected call to is_dir()")

        def mock_read_text(self: Path):
            """Mocked directory check"""
            raise FileNotFoundError("Mock Path.resolve()")

        monkeypatch.setattr(ToolGroup, "verify_tool_group", self.mock_verify_tool_group)
        monkeypatch.setattr(os, "listdir", lambda path: [])
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "read_text", mock_read_text)
        tg = ToolGroup("tool-group")
        assert tg.trigger is None
        assert tg.name == "tool-group"
        assert tg.get_label("hostname") == ""
        assert tg.get_tools("hostname") == {}

    def test_tool_group_dir(self, monkeypatch):
        """Verify ToolGroup class normal operation"""

        tool_group_name = "tool-group"
        tool_group_dir = Path("/mock/pbench-agent")
        trigger = "trigger file contents"
        hosts = ["host1", "host2", "host3"]

        subdirs = {
            tool_group_dir / "host1": ["tool2", "tool3", "dir__noinstall__"],
            tool_group_dir / "host2": ["tool1", "__label__", "dir__noinstall__"],
            tool_group_dir / "host3": ["tool1", "tool2", "tool3", "__label__"],
        }
        opt_template = "tool opts for {}/{}"
        tools = {
            "host1": {
                "tool2": opt_template.format("host1", "tool2"),
                "tool3": opt_template.format("host1", "tool3"),
            },
            "host2": {
                "tool1": opt_template.format("host2", "tool1"),
            },
            "host3": {
                "tool1": opt_template.format("host3", "tool1"),
                "tool2": opt_template.format("host3", "tool2"),
                "tool3": opt_template.format("host3", "tool3"),
            },
        }
        label_template = "{} label file contents"
        labels = {
            "host1": "",
            "host2": label_template.format("host2"),
            "host3": label_template.format("host3"),
        }

        hostnames = {
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

        def mock_listdir(path):
            if path == tool_group_dir:
                return hosts
            try:
                return subdirs[path]
            except KeyError as exc:
                raise AssertionError(f"Unexpected directory in listdir() mock: {exc}")

        def mock_is_dir(path):
            return str(path).startswith(str(tool_group_dir / "host"))

        def mock_read_text(path):
            if path.name == "__trigger__":
                return trigger
            if path.name == "__label__":
                return label_template.format(path.parent.name)
            if path.name[:-1] == "tool":
                return opt_template.format(path.parent.name, path.name)
            raise AssertionError(f"Unexpected file in read_text() mock: {str(path)!r}")

        monkeypatch.setattr(ToolGroup, "verify_tool_group", self.mock_verify_tool_group)
        monkeypatch.setattr(os, "listdir", mock_listdir)
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "read_text", mock_read_text)
        tg = ToolGroup(tool_group_name)
        assert tg.name == tool_group_name
        assert tg.trigger == trigger
        assert tg.hostnames == hostnames
        for host in hosts:
            assert tg.get_tools(host) == tools[host]
            assert tg.get_label(host) == labels[host]
        assert tg.get_tools("bad-host") == {}
        assert tg.get_label("bad-host") == ""
