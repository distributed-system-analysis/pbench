#!/usr/bin/env python
"""
very simplistic program to determine which of the set of arguments are
sosreport plugins which are loaded and active when sosreport is invoked.

For sosreport v3.x, we use the SoSReport class.  For v2.2 (really for
RHEL 6 systems, 6.0 thru 6.6), we just create a mock SoSReport class
that we use to do the same thing.
"""
import os
import sys
import pdb
import configparser
from collections import deque


if not len(sys.argv) > 1:
    sys.exit(0)

try:
    from sos.sosreport import SoSReport
except ImportError:
    from sos.policyredhat import SosPolicy
    from sos.helpers import importPlugin


    class WrappedSosPolicy(SosPolicy):
        def __init__(self, *args, **kwargs):
            SosPolicy.__init__(self, *args, **kwargs)

        def set_commons(self, *args, **kwargs):
            self.setCommons(*args, **kwargs)


    class SoSReport(object):
        def __init__(self, args):
            self.config = ConfigParser.ConfigParser()
            config_file = '/etc/sos.conf'
            try:
                self.config.readfp(open(config_file))
            except IOError:
                pass
            self.policy = WrappedSosPolicy()
            self.plugin_names = deque()
            self.loaded_plugins = deque()
            # find the plugins path
            self.pluginpath = ""
            paths = sys.path
            for path in paths:
                if path.strip()[-len("site-packages"):] == "site-packages" \
                        and os.path.isdir(path + "/sos/plugins"):
                    self.pluginpath = path + "/sos/plugins"

        def _setup_logging(self):
            pass

        def get_commons(self):
            return {'dstroot': '/tmp', 'cmddir': '/tmp', 'logdir': '/tmp', 'rptdir': '/tmp',
                    'soslog': None, 'proflog': None, 'policy': self.policy, 'verbosity' : False,
                    'xmlreport' : None, 'cmdlineopts': None, 'config': self.config}

        def load_plugins(self):
            # disable plugins that we read from conf files
            conf_disable_plugins_list = deque() 
            conf_disable_plugins = None
            if self.config.has_option("plugins", "disable"):
                conf_disable_plugins = self.config.get("plugins", "disable").split(',')
                for item in conf_disable_plugins:
                    conf_disable_plugins_list.append(item.strip())

            # generate list of available plugins
            plugins = os.listdir(self.pluginpath)
            plugins.sort()

            # validate and load plugin
            commons = self.get_commons()
            for plug in plugins:
                plugbase = plug[:-3]
                if not plug[-3:] == '.py' or plugbase == "__init__":
                    continue
                self.plugin_names.append(plugbase)
                try:
                    if self.policy.validatePlugin(self.pluginpath + plug):
                        pluginClass = importPlugin("sos.plugins." + plugbase, plugbase)
                    else:
                        continue
                    if plugbase in conf_disable_plugins_list:
                        continue
                    if not pluginClass(plugbase, commons).checkenabled():
                        continue
                    if not pluginClass(plugbase, commons).defaultenabled():
                        continue
                    self.loaded_plugins.append((plugbase, pluginClass(plugbase, commons)))
                except:
                    pass

        def _set_all_options(self):
            pass

        def _set_tunables(self):
            pass

        def _check_for_unknown_plugins(self):
            pass

        def _set_plugin_options(self):
            pass


sosrpt = SoSReport(None)
# THe following are basically what sosrpt.execute() does up to the point
# where it checks to see if --list-plugin is present.
sosrpt._setup_logging()
sosrpt.policy.set_commons(sosrpt.get_commons())
sosrpt.load_plugins()
sosrpt._set_all_options()
sosrpt._set_tunables()
#sosrpt._check_for_unknown_plugins()
sosrpt._set_plugin_options()

# Now that we know what plugins are available, we bump the arguments
# against the set of loaded plugins.
plugins_set = set([name for name in sosrpt.plugin_names])
loaded_plugins_set = set([name for (name, plugin) in sosrpt.loaded_plugins])
available = [arg for arg in sys.argv[1:] if arg in plugins_set and loaded_plugins_set]
if available:
    available.sort()
    print (",".join(available))
