from pbench.agent.logger import logger

def test_info(caplog):
    logger.info('foo')
    assert 'foo' in caplog.text

def test_error(caplog):
    logger.error('foo')
    assert 'foo' in caplog.text

def test_warn(caplog):
    logger.error("foo")
    assert 'foo' in caplog.text
