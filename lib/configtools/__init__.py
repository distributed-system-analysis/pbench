""" Configtools """
from __future__ import print_function

import os
import sys

# python3
from configparser import ConfigParser
from optparse import OptionParser, make_option


def uniq(l):
    # uniquify the list without scrambling it
    seen = set()
    seen_add = seen.add
    return [x for x in l if x not in seen and not seen_add(x)]


def file_list(root):
    # read the root file, get its [config] section
    # and use it to construct the file list.
    conf = ConfigParser()
    conf.read(root)
    try:
        dirlist = conf.get("config", "path").replace(" ", "").split(",")
    except Exception:
        dirlist = []
    try:
        files = conf.get("config", "files").replace(" ", "").split(",")
    except Exception:
        files = []

    root = os.path.abspath(root)
    # all relative pathnames will be relative to the rootdir
    rootdir = os.path.dirname(root)
    flist = [root]
    dirlist = [
        os.path.abspath("%s/%s" % (rootdir, x))
        if not os.path.isabs(x)
        else os.path.abspath(x)
        for x in dirlist
    ]
    # insert the directory of the root file at the beginning
    dirlist.insert(0, rootdir)

    # import pdb; pdb.set_trace()
    for d in dirlist:
        for f in files:
            fnm = "%s/%s" % (d, f)
            if fnm in flist:
                continue
            if os.access(fnm, os.F_OK):
                fnmlist = file_list(fnm)
                flist += fnmlist
    return uniq(flist)


def init(opts, env_config):
    """init"""
    # config file
    conf = ConfigParser()
    if opts.filename:
        conf_file = opts.filename
    elif env_config in os.environ:
        conf_file = os.environ[env_config]
    else:
        return (None, [])

    conffiles = file_list(conf_file)
    conffiles.reverse()
    files = conf.read(conffiles)

    return (conf, files)


def parse_args(options=[], usage=None):
    """parse_args"""
    if usage:
        parser = OptionParser(usage=usage)
    else:
        parser = OptionParser()
    # standard options
    parser.add_option(
        "-C", "--config", dest="filename", help="config FILE", metavar="FILE"
    )
    parser.add_option(
        "-D",
        "--debug",
        action="store_true",
        dest="debug",
        help="commands logged but not executed",
    )
    # specific options
    for o in options:
        parser.add_option(o)

    return parser.parse_args()


def parse_range(s):
    """s is of the form <prefix>[<range>]<suffix>.
       Parse and return the three components separately.
    """
    pos = s.find("[")
    rpos = s.find("]")
    if pos >= 0:
        prefix = s[0:pos]
        if rpos >= 0:
            rng = s[pos + 1 : rpos]
            suffix = s[rpos + 1 :]
        else:
            prefix = s
            rng = suffix = ""
    else:
        prefix = s
        rng = suffix = ""

    return (prefix, suffix, rng)


def expand_range(s):
    """Expand a range `foo[N-M]bar' or 'foo[1, 2, 3]bar' or 'foo[a, b, c]bar'
       into a list - no multiple ranges or nesting allowed.
       Always return a list, maybe a singleton if no expansion is necessary.
    """
    prefix, suffix, rng = parse_range(s)
    if not rng:
        return ["%s%s" % (prefix, suffix)]

    try:
        nfields = [x for x in rng.split("-")]
        if len(nfields) == 2:
            # expand the range
            try:
                els = map(str, range(int(nfields[0]), int(nfields[1]) + 1))
            except Exception:
                els = map(chr, range(ord(nfields[0]), ord(nfields[1]) + 1))
            return ["%s%s%s" % (prefix, x, suffix) for x in els]
        elif len(nfields) == 1:
            # split it on ,
            els = map(str.strip, rng.split(","))
            return ["%s%s%s" % (prefix, x, suffix) for x in els]
    except Exception:
        return [s]


def get_list(s):
    """get_list"""
    if not s:
        return []
    els = [x.strip().strip("\\\n") for x in s.split(",")]
    try:
        nl = []
        for x in els:
            nl += expand_range(x)
        return nl
    except Exception:
        return els


def get(conf, option, sections):
    """get option from section list"""
    for s in sections:
        try:
            return conf.get(s, option)
        except Exception:
            pass
    return None


def print_list(l, sep):
    print(sep.join([str(x) for x in l]))


options = [
    make_option(
        "-a",
        "--all",
        action="store_true",
        dest="all",
        help="print all items in section",
    ),
    make_option(
        "-d",
        "--dump",
        action="store_true",
        dest="dump",
        help="print everything and exit",
    ),
    make_option(
        "-l",
        "--list",
        action="store_true",
        dest="list",
        help="print it as a shell list, translating commas to spaces",
    ),
    make_option(
        "-L",
        "--listfiles",
        action="store_true",
        dest="listfiles",
        help="print the list of config files and exit",
    ),
]


def main(conf, args, opts, files):
    if not conf:
        status = 1
    elif opts.dump:
        conf.write(sys.stdout)
        status = 0
    elif opts.listfiles:
        files.reverse()
        print(files)
        status = 0
    elif args:
        if opts.all:
            for sec in args:
                if conf.has_section(sec):
                    print("[%s]" % (sec))
                    items = conf.items(sec)
                    items.sort()
                    for (n, v) in items:
                        print("%s = %s" % (n, v))
                    print()
            return 0

        sep = ","
        if opts.list:
            sep = " "

        option = args[0]
        for sec in args[1:]:
            if conf.has_section(sec):
                if conf.has_option(sec, option):
                    print_list(get_list(conf.get(sec, option)), sep)
                    return 0
        status = 1
    else:
        status = 1
    return status
