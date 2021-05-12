"""Test Pbench MetadataLog behaviors
"""

from pbench.common import MetadataLog


class TestMetadataLog:
    @staticmethod
    def test_ensure_no_interpolation():
        """Test to ensure interpolation is off."""
        mdlog = MetadataLog()
        mdlog.add_section("foo")
        val = "This is a % that should not fail."
        mdlog.set("foo", "bar", val)
        assert mdlog.get("foo", "bar") == val
