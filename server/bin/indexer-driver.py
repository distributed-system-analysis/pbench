#!/usr/bin/env python3

import time
import json
import os
import socket
import logging
from datetime import datetime
from pbench.indexer import ToolData
import pbench.indexer

def myopen(path, mode):
    return open(os.path.basename(path), mode)
pbench.indexer.open = myopen


class MockTarobject(object):
    def __init__(self, name):
        self.name = name
    def isfile(self):
        return True


class MockTarfile(object):
    def __init__(self):
        pass
    def getnames(self):
        return [ 'fake-dir/1-driver/sampl1/tools-default/localhost/proc-interrupts/proc-interrupts-stdout.txt' ]
    def getmember(self, x):
        return MockTarobject(x)


class MockPbenchTarBall(object):
    _formats = [ "%Y-%m-%dT%H:%M:%S.%f", "%Y%m%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y%m%dT%H:%M:%S" ]

    @staticmethod
    def convert_to_dt(dt_str):
        rts = dt_str.replace('_', 'T')
        us_offset = rts.rfind('.')
        us = rts[us_offset:][:7]
        rts = rts[:us_offset] + us
        for f in MockPbenchTarBall._formats:
            try:
                dt = datetime.strptime(rts, f)
            except ValueError:
                continue
            else:
                return dt, dt.isoformat()
        else:
            raise Exception()

    def __init__(self, idxctx, tbarg, tmpdir, extracted_root):
        self.idxctx = idxctx
        self.tbname = tbarg
        self.extracted_root = extracted_root
        self.controller_dir = 'fake-controller'
        self.satellite = None
        self.controller_name = self.controller_dir
        self.tb = MockTarfile()
        self.dirname = 'fake-dir'
        self.mdconf = None
        self.start_run_ts, self.start_run = MockPbenchTarBall.convert_to_dt('2019-04-02T12:00:00')
        self.end_run_ts, self.end_run = MockPbenchTarBall.convert_to_dt('2019-04-03T13:00:00')
        self.at_metadata = dict([
                ('file-date', 'today'),
                ('file-name', self.tbname),
                ('file-size', 42),
                ('md5', 'fake-md5sum'),
                ('toc-prefix', self.dirname)
            ])
        self.run_metadata = dict([
                ('controller', 'faker'),
                ('name', self.tbname),
                ('script', 'indexer-driver'),
                ('toolsgroup', 'default'),
                ('start', self.start_run),
                ('end', self.end_run),
                ('date', self.end_run_ts.isoformat()),
                ('id', 'fake-md5sum')
            ])

class MockIdxContext(object):
    def __init__(self, options, name, _dbg=0):
        self.options = options
        self.name = name
        self._dbg = _dbg
        self.opctx = []
        self.confg = None
        self.idx_prefix = 'indexer-driver'
        self.time = time.time
        self.gethostname = socket.gethostname
        self.getpid = os.getpid
        self.getgid = os.getgid
        self.getuid = os.getuid
        self.TS = 'TS'
        self.logger = logging.getLogger('indexer-driver')
        self.es = None
        self.templates = None
        self.tracking_id = None

    def dump_opctx(self):
        counters_list = []
        for ctx in self.opctx:
            if ctx['counters']:
                counters_list.append(ctx)
        if counters_list:
            self.logger.warning("** Errors encountered while indexing: {}",
                    json.dumps(counters_list, sort_keys=True))

    def set_tracking_id(self, tid):
        self.tracking_id = tid

    def get_tracking_id(self):
        return self.tracking_id


initial = time.time()

ctx = MockIdxContext(None, 'driver')
ptb = MockPbenchTarBall(ctx, 'fake', 'tmpdir', '../../../../../..')

td = ToolData(ptb, '1-driver', 'sampl1', 'localhost', 'proc-interrupts', ctx)
print("{!r}".format(td.files))
asource = td.make_source()

# We time the generator execution, nothing happens until we start processing.
start = time.time()
count = 0
for source, source_id in asource:
    count += 1
end = time.time()

print("Generated {:d} records in {:0.2f} seconds ({:0.2f}).".format(count, (end - start), (start - initial)))
