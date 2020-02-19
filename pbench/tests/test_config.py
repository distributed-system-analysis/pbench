import os
import shutil
import tempfile

from oslotest import base
import pytest

from pbench.common import config
from pbench.common import exceptions

class TestPbenchConfig(base.BaseTestCase):
    def setUp(self):
        super(TestPbenchConfig, self).setUp()
        self.testdir = tempfile.mkdtemp()

    def test_config_get(self):
        fake_content = """
        [pbench-agent]
        pbench_run = /var/lib/pbench-agent
        """
        pbench_config = os.path.join(self.testdir, 'pbench_agent.cfg_name')
        with open(pbench_config, 'w+') as f:
            f.write(fake_content)
        os.environ['CONFIG'] = pbench_config

        c = config.PbenchConfig()
        self.assertEqual('/var/lib/pbench-agent', 
            c.get('pbench-agent', 'pbench_run'))

    def test_missing_config(self):
        with pytest.raises(exceptions.PbenchMissingConfig):
            config.PbenchConfig(cfg_name='/fake/pbench-agent.cfg')

    def test_show_config(self):
        fake_content = """
        [DEFAULT]
        """
        pbench_config = os.path.join(self.testdir, 'pbench_agent.cfg_name')
        with open(pbench_config, 'w+') as f:
            f.write(fake_content)

        os.environ['CONFIG'] = pbench_config
        c = config.PbenchConfig()
        self.assertEqual(c.show_config(),
            pbench_config)

    def test_invalid_config(self):
        fake_content = "fake_config"

        with pytest.raises(exceptions.PbenchInvalidConfiguration):
            pbench_config = os.path.join(self.testdir, 'invalid_config')
            with open(pbench_config, 'w+') as f:
                f.write(fake_content)

            os.environ['CONFIG'] = pbench_config
            c = config.PbenchConfig()

