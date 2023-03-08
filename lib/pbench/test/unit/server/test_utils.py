from dateutil import parser as date_parser
import pytest

from pbench.server.utils import UtcTimeHelper


class TestUtcTimeHelper:
    @pytest.mark.parametrize(
        "source,iso",
        [
            ("1970-01-01T00:00:00", "1970-01-01T00:00:00+00:00"),
            ("2002-05-16T10:23+00:00", "2002-05-16T10:23:00+00:00"),
            ("2002-05-16T10:23-04:00", "2002-05-16T14:23:00+00:00"),
            ("2020-12-16T09:00:53+05:30", "2020-12-16T03:30:53+00:00"),
        ],
    )
    def test_timehelper(self, source, iso):
        d1 = UtcTimeHelper(date_parser.parse(source))
        d2 = UtcTimeHelper.from_string(source)
        assert d1.to_iso_string() == d2.to_iso_string()
        assert d1.utc_time == d2.utc_time
        assert d1.to_iso_string() == iso
        assert d1.utc_time.isoformat() == d1.to_iso_string()
