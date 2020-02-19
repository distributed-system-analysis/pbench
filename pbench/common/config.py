import configparser
import logging
import os
import sys

import configtools

from pbench.common import exceptions

LOG = logging.getLogger(__name__)

class PbenchConfig(object):
    """ Parse pbench configuration file """

    def __init__(self, cfg_name=None):
        if not cfg_name:
            config_name = os.environ.get('CONFIG')
            if config_name:
                self.cfg_name = config_name
        else:
            self.cfg_name = cfg_name

        if not os.path.exists(self.cfg_name):
            raise exceptions.PbenchMissingConfig(self.cfg_name)

        try:
            self.config_files = configtools.file_list(self.cfg_name)
            self.config_files.reverse()
            self.conf = configparser.SafeConfigParser()
            self.conf.read(self.config_files)
        except Exception:
            raise exceptions.PbenchInvalidConfiguration(self.cfg_name)

    def get(self, *args, **kwargs):
        """Get the key, value configuration from a configuration file"""
        return self.conf.get(*args, **kwargs)

    def dump_config(self):
        """Display the pbench configuration file for the user"""
        for section in self.conf.sections():
            print("\n[%s]" % section)
            items = self.conf.items(section)
            for (n, v) in items:
                print("%s = %s" % (n, v))

    def dump_section(self, section):
        """Display the pbench config section desired"""
        if not self.conf.has_section(section):
            raise exceptions.PbenchNoSuchOption(section)

        print("\n[%s]" % section)
        items = self.conf.items(section)
        for (n, v) in items:
             print("%s = %s" % (n, v))

    def show_config(self):
        """Display the path of the pbench configuration"""
        return self.cfg_name
