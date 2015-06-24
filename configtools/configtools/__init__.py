""" Configtools """
from __future__ import print_function

import os, sys

try:
    # python3
    from configparser import SafeConfigParser
except:
    from ConfigParser import SafeConfigParser
    
from optparse import OptionParser

import logging

def uniq(l):
    # uniquify the list without scrambling it
    seen = set()
    seen_add = seen.add
    return [x for x in l if x not in seen and not seen_add(x)]

def file_list(root):
    # read the root file, get its [config] section
    # and use it to construct the file list.
    conf = SafeConfigParser()
    conf.read(root)
    try:
        dirlist = conf.get("config", "path").replace(' ', '').split(',')
    except:
        dirlist = []
    try:
        files = conf.get("config", "files").replace(' ', '').split(',')
    except:
        files = []

    
    root = os.path.abspath(root)
    # all relative pathnames will be relative to the rootdir
    rootdir = os.path.dirname(root)
    flist = [root]
    dirlist = [os.path.abspath("%s/%s" % (rootdir, x)) if not os.path.isabs(x) else os.path.abspath(x) for x in dirlist]
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

def init(opts):
    """init"""
    # config file
    conf = SafeConfigParser()
    if opts.filename:
        conf_file = opts.filename
    elif 'CONFIG' in os.environ:
        conf_file= os.environ['CONFIG']
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
    parser.add_option("-C", "--config", dest="filename",
                  help="config FILE", metavar="FILE")
    parser.add_option("-D", "--debug", action="store_true", dest="debug",
                      help="commands logged but not executed")
    # specific options
    for o in options:
        parser.add_option(o)

    return parser.parse_args()

def expand_range(s):
    """expand a range `N-M' into a list (of integers - arguably 
    it should expand a range of chars as well, but it doesn't.)"""
    
    try:
        nfields = [int(x) for x in s.split('-')]
        if len(nfields) == 2:
            #return [str(x) for x in range(nfields[0], nfields[1]+1)]
            return range(nfields[0], nfields[1]+1)
        elif len(nfields) == 1:
            return [int(s)]
    except:
        return [s]

def get_list(s):
    """get_list"""
    if not s:
        return []
    l = [x.strip().strip('\\\n') for x in s.split(',')]
    try:
        nl = []
        for x in l:
            nl += expand_range(x)
        return nl
    except:
        return l

def get(conf, option, sections):
    """get option from section list"""
    for s in sections:
        try:
            return conf.get(s, option)
        except:
            pass
    return None

def get_debug(conf, section="DEFAULT", opts=None):
    if opts and opts.debug:
        return True
    try:
        return int(conf.get(section, "debug")) > 0
    except:
        return False

def print_list(l, sep):
    print(sep.join([str(x) for x in l]))

def get_host_classes(conf):
    hostclasses = conf.options("hosts")
    # remove DEFAULT options
    for h in hostclasses:
        if conf.has_option(None, h):
            hostclasses.remove(h)
    return hostclasses

def log(cmd):
    logging.debug("%s: %s" % (hostname, cmd))
    logflush()
    
def logflush():
    logging.getLogger().handlers[0].flush()
    
def do_cmd(cmd, dbg=False):
    status = 0
    log(cmd)
    if not dbg:
        status = os.system(cmd)
    return os.WEXITSTATUS(status)

def do_cmd_with_stdout(cmd, dbg=False):
    import subprocess

    log(cmd)
    if not dbg:
        p = subprocess.Popen(cmd.split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)
        p.wait()
        return p.stdout.read()
    else:
        return ""

