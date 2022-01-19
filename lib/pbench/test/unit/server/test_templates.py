import datetime
import io
from pathlib import Path

import pytest

from pbench.server.templates import JsonFile, JsonToolFile


@pytest.fixture()
def fake_resolve(monkeypatch):
    """
    JsonFile objects use Path().resolve(strict=True) to get a full path; fake
    it so we don't need real files.

    Args:
        monkeypatch: Patching fixture
    """

    def fake_resolve(self: Path, strict: bool = False):
        """
        Return a "full" fake file name

        Args:
            strict: Not used in the mock

        Returns:
            new Path with fake resolution
        """
        return Path("/fake/path/") / self.name

    with monkeypatch.context() as m:
        m.setattr(Path, "resolve", fake_resolve)
        yield


@pytest.fixture()
def fake_open(monkeypatch, request):
    """
    JsonFile objects use Path().resolve(mode="r") to read the JSON file; fake
    it so we don't need real files.

    Args:
        monkeypatch: Patching fixture
    """
    data = request.node.get_closest_marker("open_data")
    if data is None:
        data = "{'default': 'test'}"

    def fake_open(self: Path, mode: str = "r"):
        """
        Return an IO stream

        Args:
            mode: file mode (assumed to be "r")

        Returns:
            IO channel from string
        """
        assert mode == "r"
        return io.StringIO(data)

    with monkeypatch.context() as m:
        m.setattr(Path, "open", fake_open)
        yield


class TestJsonFile:
    """
    Tests for the JsonFile class
    """

    def test_json_file(self, fake_resolve, fake_mtime):
        """
        Test a simple object construction
        """
        json = JsonFile(Path("mapping.json"))
        assert str(json.file) == "/fake/path/mapping.json"
        assert json.json is None
        assert json.modified == datetime.datetime(2021, 1, 29, 0, 0, 0)

    def test_json_load(self, monkeypatch, fake_resolve, fake_mtime):
        """
        Test "loading" a JsonFile object from a fake JSON file to verify that
        the JSON content and version are processed properly.
        """
        json = JsonFile(Path("mapping.json"))
        with monkeypatch.context() as m:

            def fake_open(self: Path, mode: str = "r"):
                return io.StringIO('{"_meta": {"version": 6}}\n')

            m.setattr(Path, "open", fake_open)
            json.load()
        assert json.get_version() == 6
        assert json.json == {"_meta": {"version": 6}}

    def test_json_add(self):
        """
        Test that JSON "mapping" properties file can be patched into the main
        JSON document.
        """
        expected = {"properties": {"bar": "string"}}
        now = datetime.datetime.now()
        json = JsonFile.raw_json(expected, now)
        assert json.json == expected
        json.add_mapping("iostat", {"run": "no"})
        assert json.json["properties"]["iostat"] == {"run": "no"}
        assert json.modified == now


class TestJsonToolFile:
    """
    Test the JsonToolFile subclass.
    """

    def test_json_file(self, fake_resolve, fake_mtime):
        """
        Test a simple object construction
        """
        json = JsonToolFile(Path("mapping.json"))
        assert str(json.file) == "/fake/path/mapping.json"
        assert json.json is None
        assert json.modified == datetime.datetime(2021, 1, 29, 0, 0, 0)

    def test_json_load(self, fake_resolve, fake_mtime, monkeypatch):
        """
        Test "loading" a JsonToolFile object from a fake JSON file to verify
        that the JSON content and version are processed properly. Unlike the
        base class, this sequesters the "_meta" version information to be
        patched into a merged skeleton/tool document.
        """
        json = JsonToolFile(Path("mapping.json"))
        with monkeypatch.context() as m:

            def fake_open(self: Path, mode: str = "r"):
                return io.StringIO('{"_meta": {"version": 6}}\n')

            m.setattr(Path, "open", fake_open)
            json.load()
        assert json.get_version() == 6

        # The "_meta" is sequestered, so we shouldn't see it
        assert json.json == {}
        assert json.meta == {"version": 6}

    def test_json_merge(self, fake_resolve, fake_mtime, monkeypatch):
        """
        Test merging a tool properties file with a skeleton file
        """
        json = JsonToolFile(Path("mapping.json"))
        base = JsonFile(Path("tool.json"))
        with monkeypatch.context() as m:

            def fake_open(self: Path, mode: str = "r"):
                return io.StringIO(
                    '{"_meta": {"version": 6}, "iostat": {"run": "far and fast"}}\n'
                )

            m.setattr(Path, "open", fake_open)
            json.load()
        with monkeypatch.context() as m:

            def fake_open(self: Path, mode: str = "r"):
                return io.StringIO('{"properties": {"@meta": "at meta friend"}}')

            m.setattr(Path, "open", fake_open)
            base.load()
        json.merge("tool", base)
        assert json.get_version() == 6
        assert json.json == {
            "_meta": {"version": 6},
            "properties": {
                "@meta": "at meta friend",
                "tool": {"iostat": {"run": "far and fast"}},
            },
        }
