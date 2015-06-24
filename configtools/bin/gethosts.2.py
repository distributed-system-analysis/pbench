#! /usr/bin/env python
from __future__ import print_function

import sys
import os
import configtools 
from optparse import make_option

def main(conf, args, opts):
    if not conf:
        return 1

    sep = ','
    if opts.list:
        sep = ' '

    hostclasses = configtools.get_host_classes(conf)
    if opts.listclasses:
        configtools.print_list(hostclasses, sep)
        return 0

    # all hosts
    if len(args) == 1 and args[0] == 'all':
        opts.all = True
    if opts.all:
        hosts = []
        for hostclass in hostclasses:
            hosts.extend(configtools.get_list(conf.get("hosts", hostclass)))
        configtools.print_list(hosts, sep)
        return 0

    # hosts in a single class
    if opts.listclass in hostclasses:
        hosts = configtools.get_list(conf.get("hosts", opts.listclass))
        configtools.print_list(hosts, sep)
        return 0

    # otherwise all the args should be classes: gather up their hosts:
    hosts = []
    for a in args:
        if a in hostclasses:
            hosts.extend(configtools.get_list(conf.get("hosts", a)))
        else:
            return 1
    configtools.print_list(hosts, sep)
    return 0

options = [
    make_option("-a", "--all", action="store_true", dest="all", help="print all hosts in all classes"),
    make_option("-l", "--list", action="store_true", dest="list", help="print it as a shell list, translating commas to spaces"),
    make_option("-L", "--listclasses", action="store_true", dest="listclasses", help="print the list of host classes"),
    make_option("-c", "--class", action="store", dest="listclass", help="print the list of hosts in a host class"),
]

if __name__ == '__main__':
    opts, args = configtools.parse_args(options)
    conf, files = configtools.init(opts)
    status = main(conf, args, opts)
    sys.exit(status)
