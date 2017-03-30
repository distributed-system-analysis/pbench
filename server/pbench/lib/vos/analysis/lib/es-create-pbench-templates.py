#!/usr/bin/env python3
#
# usage:
# $ python3 es-create-pbench-templates.py

import os
import sys
import configparser
import glob
import json
from elasticsearch import Elasticsearch

cfg_name = "/etc/pbench-index.cfg"

config = configparser.ConfigParser()
config.read(cfg_name)

try:
    URL = config.get('ElasticSearch', 'server')
except configparser.NoSectionError:
    print("Need a [ElasticSearch] section with host and port defined in %s"
          " configuration file" % cfg_name, file=sys.stderr)
except configparser.NoOptionError:
    host = config.get('ElasticSearch', 'host')
    port = config.get('ElasticSearch', 'port')
else:
    host, port = URL.rsplit(':', 1)
hosts = [dict(host=host, port=port), ]
INDEX_PREFIX = config.get('Settings', 'index_prefix')
SAR_VERSION = config.get('Settings', 'sar_template_version')


def fetch_mapping(mapping_fn):
    with open(mapping_fn, "r") as mappingfp:
        try:
            mapping = json.load(mappingfp)
        except ValueError as err:
            print("%s: %s" % (mapping_fn, err), file=sys.stderr)
            sys.exit(1)
    keys = list(mapping.keys())
    if len(keys) != 1:
        print("Invalid mapping file: %s" % mapping_fn, file=sys.stderr)
        sys.exit(1)
    return keys[0], mapping


LIBDIR = './'

key, mapping = fetch_mapping(os.path.join(LIBDIR, "sar_mapping.json"))

sar_mappings = {key: mapping}
sar_body = dict(
    template='%s.sar-*' % (INDEX_PREFIX,),
    mappings=sar_mappings)

es = Elasticsearch(hosts)


def create_template(tname, tbody):
    if es.indices.exists_template(name=tname):
        return
    try:
        res = es.indices.put_template(name=tname, body=tbody)
    except Exception as err:
        print(repr(err), file=sys.stderr)
        sys.exit(1)
    else:
        try:
            if not res['acknowledged']:
                print('ERROR - Template creation was not acknowledged', file=sys.stderr)
                sys.exit(1)
        except KeyError:
            print('ERROR - Template creation failed: %r' % res, file=sys.stderr)
            sys.exit(1)
        print("Created template %s" % tname)

tname = '%s.sar-%s' % (INDEX_PREFIX, SAR_VERSION)
sar_body['template'] = '%s.sar-*' % (INDEX_PREFIX,)
create_template(tname, sar_body)
