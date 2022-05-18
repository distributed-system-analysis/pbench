#!/usr/bin/env python3
# Copyright 2018 The MLPerf Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

import os
import sys
import re
import time
import datetime
import argparse
import json
import pprint
import time
import importlib
import hashlib

# See https://stackoverflow.com/questions/10415028/how-can-i-recover-the-return-value-of-a-function-passed-to-multiprocessing-proce
# For error handling: https://stackoverflow.com/questions/19924104/python-multiprocessing-handling-child-errors-in-parent
import multiprocessing 

DEFAULT_SAMPLING_INTERVAL = 2
DEFAULT_SAMPLING_DURATION = 300

class SampleMetrics():
    def __init__(self,
                 f_objects,
                 sampler_modules,
                 sampling_interval,
                 sampling_duration,
                 verbose = 0):
        self._f_objects = f_objects
        self._sampler_modules = sampler_modules

        #my_name=os.path.abspath(__file__)
        my_name=__file__
        with open(my_name) as f:
            data = f.read()
            sha1 = hashlib.sha1(str(data).encode('utf-8')).hexdigest()
            self.write("SHA1, %s %s" % (os.path.basename(my_name), sha1),
                       f_out=self._f_objects["f_log"])

        self._samplers = {}
        for m in self._sampler_modules:
            self._samplers[m]=m.Sampler()
            my_name=m.__file__
            with open(my_name) as f:
                data = f.read()
                sha1 = hashlib.sha1(str(data).encode('utf-8')).hexdigest()
                self.write("SHA1, %s %s" % (os.path.basename(my_name), sha1),
                                           f_out=self._f_objects["f_log"])

        self._sampling_interval = sampling_interval
        self.write("PARAMETER, sampling_interval %s" % self._sampling_interval,
                   f_out=self._f_objects["f_log"])
        self._sampling_duration = sampling_duration
        self.write("PARAMETER, sampling_duration %s" % self._sampling_duration,
                   f_out=self._f_objects["f_log"])
        self._verbose = verbose
        self._error = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close_samplers()

    def close_samplers(self):
        for m in self._sampler_modules:
            if self._verbose > 1:
                self.write("Delete sampler: %s" % m.__name__)
            sampler = self._samplers[m].close()
        self._sampler_modules = None

    def write(self, simple_string, f_out=None, prefix = "", suffix = "\n"):
        if not f_out:
            f_out=self._f_objects["f_out"]
        f_out.write("%s%s%s" % (prefix, simple_string, suffix))
        f_out.flush()

    def write_csv(self, items, f_log):
        if f_log:
            s = "CSV"
            for item in items:
                s = "%s, %s" % (s, item)
            f_log.write("%s\n" % s)
            f_log.flush()

    def get_titles(self, titles0=[]):
        titles=list(titles0)
        for m in self._sampler_modules:
            sampler = self._samplers[m]
            titles.extend(sampler.get_titles())
            if self._verbose>1:
                self.write("Add sampler: %s" % m.__name__)
                self.write(" Titles: %s" % (titles,))
        return titles

    def get_values(self, values0=[]):
        values=list(values0)
        for m in self._sampler_modules:
            sampler = self._samplers[m]
            values.extend(sampler.get_values())
            if self._verbose>1:
                self.write("Add sampler: %s" % m.__name__)
                self.write(" Values: %s" % (values,))
        return values

    @staticmethod
    def _worker(func, values_dict, m):
        values_dict[m.__name__] = func()
        
    def get_values_multiprocessing(self, values0=[]):
        manager = multiprocessing.Manager()
        values_dict = manager.dict()
        pm=[]
        for m in self._sampler_modules:
            sampler = self._samplers[m]
            p = multiprocessing.Process(target=self._worker,
                                        args=[sampler.get_values, values_dict, m])
            p.start()
            pm.append((p, m))

        for p, m in pm:
            p.join()

        values = list(values0)
        for p, m in pm:
            values.extend(values_dict[m.__name__])
            if self._verbose>1:
                self.write("Add sampler: %s" % m.__name__)
                self.write(" Values: %s" % (values,))

        return values

    def run(self):
        titles = self.get_titles(["epoch"])
        self.write_csv(titles, self._f_objects["f_log"])
        self._error = 0
        time0 = time.time()
        time1 = None
        delta_time = 0
        ii = 0
        self._num_sample_cycles = 0
        while delta_time <= self._sampling_duration:
            current_time = time.time()
            try:
                remaining_time = self._sampling_interval - (current_time-time1)
            except TypeError:
                remaining_time = 0
            if remaining_time <= 0:
                time1 = current_time
                #values=self.get_values([current_time])
                values=self.get_values_multiprocessing([current_time])
                self.write_csv(values, self._f_objects["f_log"])
                self._num_sample_cycles += 1
                if self._verbose>0:
                    self.write("Number of Samples Cycles completed: %d" % self._num_sample_cycles)
                    self.write("Total Time in Seconds: %f\n" % (time.time()-time0))
            elif remaining_time > 0.01:
                time.sleep(remaining_time/2.0)
                
            delta_time = time.time()-time0

        return self._error

    def error(self):
        return self._error

def valid_dir_path(string):
    path = os.path.realpath(string)
    if not os.path.isdir(path):
        msg = "%r not a valid directory" % path
        raise argparse.ArgumentTypeError(msg)
    return path

def positive_int(string):
    value = int(string)
    if value<1:
        msg = "%r not a postive integer" % string
        raise argparse.ArgumentTypeError(msg)
    return value

def parse():
    my_path = os.path.dirname(os.path.realpath(__file__))

    parser = argparse.ArgumentParser()

    parser.add_argument("-I", "--sampling_interval", type = positive_int,
                        action = "store", default = DEFAULT_SAMPLING_INTERVAL,
                        help = "Sampling Interval (sec)")

    parser.add_argument("-D", "--sampling_duration", type = positive_int,
                        action = "store", default = DEFAULT_SAMPLING_DURATION,
                        help = "Sampling Duration (sec)")

    parser.add_argument("-o", "--outfile",
                        action = "store", default = None,
                        help = "Output file")

    parser.add_argument("-l", "--logfile",
                        action = "store", default = None,
                        help = "Comma Separated Variable result")

    parser.add_argument("-v", "--verbose",
                        action = "count", default = 0,
                        help = "Increase output verbosity")

    parser.add_argument('sampler_name', nargs = '+',
                        help = 'Python sampler class to instantiate')

    args = parser.parse_args()

    sampler_modules = []
    for sampler_name in args.sampler_name:
        #m=importlib.import_module(sampler_name, package=None)
        m=importlib.import_module(sampler_name)
        sampler_modules.append(m)

    f_objects={}

    if args.outfile:
        f_objects["f_out"] = open(args.outfile, 'w')
    else:
        f_objects["f_out"] = sys.stdout

    if args.logfile:
        f_objects["f_log"] = open(args.logfile, 'w')
    else:
        f_objects["f_log"] = sys.stdout

    if args.verbose>0:
        try:
            f_objects["f_out"].write("args:\n")
            pprint.pprint(vars(args), stream = f_objects["f_out"])
        except TypeError:
            pass

    return (f_objects, args, sampler_modules)

if __name__ == '__main__':
    f_objects, args, sampler_modules = parse()
    with SampleMetrics(f_objects=f_objects,
                       sampler_modules=sampler_modules,
                       sampling_interval=args.sampling_interval,
                       sampling_duration=args.sampling_duration,
                       verbose=args.verbose) as sm:
        sm.run()
        sys.exit(sm.error())

