"""Tests for validate_hostname
"""

from pbench.common.utils import validate_hostname


def test_validate_hostname():
    assert validate_hostname("test") == 0
    assert validate_hostname("test.example.com") == 0
    assert validate_hostname("tes_t.example.com") == 1
    assert validate_hostname("test-.example.com") == 1
    assert validate_hostname("--run-label__") == 1
    assert validate_hostname("127.0.0.1") == 0
    assert validate_hostname("1270.0.0.1") == 0
    assert validate_hostname("2001:0db8:85a3:0000:0000:8a2e:0370:7334") == 0
