#! /usr/bin/env python
from __future__ import print_function

import sys
import os
import configtools 
from optparse import make_option

def main(conf, args, opts):
    if not conf:
        return 1

    if opts.dump:
        conf.write(sys.stdout)
        return 0

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

    sep = ','
    if opts.list:
        sep =  ' '

    if args:
        option = args[0]
        for sec in args[1:]:
            if conf.has_section(sec):
                if conf.has_option(sec, option):
                    configtools.print_list(configtools.get_list(conf.get(sec, option)), sep)
                    return 0
    return 1

options = [
    make_option("-a", "--all", action="store_true", dest="all", help="print all items in section"),
    make_option("-d", "--dump", action="store_true", dest="dump", help="print everything"),
    make_option("-l", "--list", action="store_true", dest="list", help="print it as a shell list, translating commas to spaces"),
    make_option("-L", "--listfiles", action="store_true", dest="listfiles", help="print the list of config files"),
]

if __name__ == '__main__':
    opts, args = configtools.parse_args(options, usage='Usage: getconf.py [options] <item>|-a <section> [<section> ...]')
    conf, files = configtools.init(opts)
    if opts.listfiles:
        files.reverse()
        print(files)
        sys.exit(0)
    status = main(conf, args, opts)
    sys.exit(status)
