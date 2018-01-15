#!/usr/bin/env python
""" Constructs an fio job file with the following precedence
    from high to low:

        - Common options, given on command line (-bs, -rw, ...)
        - Job file, given with '-j'.

    Fio job files may contain references to:

        - '$target', which is replaced sequentially with each instance of the
          targets specified with '-targets'.
        - '$@', which is replaced by the command line parameter to this
          program by the same name.

"""
import sys
from collections import OrderedDict
try:
    from configparser import SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser

try:
    SafeConfigParser.read_dict
except AttributeError:

    # Taken from configparser 3.5.0-py2.7 with minor modifications:
    def _read_dict(self, dictionary, source='<dict>'):
        """Read configuration from a dictionary.

        Keys are section names, values are dictionaries with keys and values
        that should be present in the section. If the used dictionary type
        preserves order, sections and their keys will be added in order.

        All types held in the dictionary are converted to strings during
        reading, including section names, option names and keys.

        Optional second argument is the `source' specifying the name of the
        dictionary being read.
        """
        elements_added = set()
        for section, keys in dictionary.items():
            section = str(section)
            try:
                self.add_section(section)
            except (DuplicateSectionError, ValueError):
                if section in elements_added:
                    raise
            elements_added.add(section)
            for key, value in keys.items():
                key = self.optionxform(str(key))
                if value is not None:
                    value = str(value)
                if (section, key) in elements_added:
                    raise DuplicateOptionError(section, key, source)
                elements_added.add((section, key))
                self.set(section, key, value)

    SafeConfigParser.read_dict = _read_dict

def parse_config(filename):
    cp = SafeConfigParser(allow_no_value=True)
    cp.read(filename)
    return cp._sections

def write_config(dictionary, out=sys.stdout):
    cp = SafeConfigParser(allow_no_value=True)
    cp.read_dict(dictionary)
    cp.write(out)

def replace_all(dct, old, new):
    """ Replace all instances of string 'old' with string 'new' in
        both keys and values of the (possibly nested) dictionary """
    keys = list(dct.keys())
    for k in keys:
        if isinstance(dct[k], dict):
            dct[k] = replace_all(dct[k], old, new)
        elif dct[k] is not None:
            old_val = dct[k]
            del dct[k]
            k = k.replace(old, new)
            dct[k] = old_val.replace(old, new)

def replace_val(dct, magic, delta):
    """ Replace all values of string 'magic' with the new value
        given by the same key in dict 'delta', in the possibly nested
        dictionary dct """
    keys = list(dct.keys())
    for k in keys:
        if isinstance(dct[k], dict):
            dct[k] = replace_val(dct[k], delta)
        else:
            if (dct[k] is not None) and magic in dct[k]:
                dct[k] = dct[k].replace(magic, delta[k])

# Other arguments that can override those given in the job file:
other_args = \
    ['bs', 'rw', 'ioengine', 'iodepth', 'direct', 'sync',
     'runtime', 'ramptime', 'size', 'rate_iops', 'log_hist_msec']

def main(ctx):

    cfg = parse_config(ctx.job_file)

    _delta = {
        'bs' : ctx.bs,
        'rw' : ctx.rw,
    }

    # Expand targets for each job file section with '$target' in the name:
    jobfile = OrderedDict()
    for target in ctx.targets:
        for k,v in cfg.items():
            if '$target' in k:
                key = k.replace('$target', target)
            else:
                key = k
            jobfile[key] = cfg[k].copy()
            replace_val(jobfile[key], '$@', _delta)
            replace_all(jobfile[key], '$target', target)

    # Override job file options with command line options:
    for a in other_args:
        val = ctx.__dict__[a]
        if not (val is None or val is ""):
            for k in jobfile.keys():
                if a in jobfile[k]: # has_key(a)
                        jobfile[k][a] = val

    write_config(jobfile)

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    arg = p.add_argument
    arg('-j', '--job_file', required=False,
        default=None,
        help='Fio job file options. Defaults to agent/bench-scripts/templates/fio.defaults.')
    arg('-targets', required=True, help='fio target device', nargs='+')
    for a in other_args:
        arg('-%s' % a, required=(a in ['bs', 'rw']), default=None, help=a)
    main(p.parse_args())

