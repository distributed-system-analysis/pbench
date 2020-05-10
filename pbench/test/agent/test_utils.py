import pytest

from pbench.lib.agent import utils


def test_sysexit():
    with pytest.raises(SystemExit) as e:
        utils.sysexit()

    assert 1 == e.value.code


def test_sysexit_with_custom_code():
    with pytest.raises(SystemExit) as e:
        utils.sysexit(2)

    assert 2 == e.value.code


def test_sysexit_with_message(mocker):
    with pytest.raises(SystemExit) as e:
        utils.sysexit_with_message("foo")

    assert 1 == e.value.code
