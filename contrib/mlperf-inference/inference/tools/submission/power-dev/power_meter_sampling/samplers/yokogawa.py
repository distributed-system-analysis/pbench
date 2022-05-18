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

# Make sure to install python3-pyvisa-py on the system from which this is run.
# Needed for "import pyvisa"
# Try apt install python3-pyvisa-py or pip install -U pyvisa

# For VISA refernece, see the following pages:
#   https://pyvisa.readthedocs.io/en/latest/
#   https://en.wikipedia.org/wiki/Virtual_instrument_software_architecture
#
# Code was developed for and tested on a Yokogawa WT333E Meter.
# For list of remote commands, see
#   WT310E/WT310EH/WT332E/WT333E Digital Power Meter
#   Communication Interface User’s Manual, IM WT310E-17EN
#   https://cdn.tmi.yokogawa.com/IMWT310E-17EN.pdf

import os
import sys
import time
import pprint
import pyvisa
import json
import inspect

class Sampler():
    def __init__(self, meter_ip = None):
        parm_file = os.path.splitext(inspect.getfile(Sampler))[0] + ".json"
        try:
            with open(parm_file) as f_json:
                self._parameters = json.load(f_json)
        except FileNotFoundError:
            self._parameters = []
        if meter_ip:
            self._meter_ip = meter_ip
        elif "meter_ip" in self._parameters:
            self._meter_ip = self._parameters["meter_ip"]
        else:
            sys.stdout.write("ERROR: must set meter_ip in %s\n" % parm_file)
            sys.exit(1)

        if "titles" in self._parameters and "elements" in self._parameters:
            self._titles = tuple(self._parameters["titles"])
            elements=[]
            for e in self._parameters["elements"]:
                try:
                    i=int(e)
                except ValueError:
                    s="ERROR: Elements must be integers (not %s)\n" % e
                    sys.stdout.write(s)
                    sys.exit(1)
                if i<1 or i>3:
                    s="ERROR: Elements 1, 2 or 3 (not %d)\n" % i
                    sys.stdout.write(s)
                    sys.exit(1)
                elements.append(i)
            self._elements = tuple(elements)
        else:
            sys.stdout.write("ERROR: must set titles and elements in %s\n" % parm_file)
            sys.exit(1)

        self._address = "TCPIP::%s::INSTR" % self._meter_ip
        self._rm = pyvisa.ResourceManager('@py')
        self._meter = self._rm.open_resource(self._address)

    def close(self):
        """Required: called before shutdown for general cleanup"""
        self._meter.close()
        self._meter=None
        self._rm.close()
        self._rm=None

    def _query(self, command):
        return self._meter.query(command)

    def get_current_range(self):
        command=":INPUT:CURRENT:RANGE?"
        return self._query(command)

    def get_voltage_range(self):
        command=":INPUT:VOLTAGE:RANGE?"
        return self._query(command)

    def get_current(self, element):
        index={1: 2, 2: 12, 3: 22}
        command=":Numeric:Normal:VALue? %d" % index[element]
        return float(self._query(command))

    def get_voltage(self, element):
        index={1: 1, 2: 11, 3: 21}
        command=":Numeric:Normal:VALue? %d" % index[element]
        return float(self._query(command))

    def get_power(self, element):
        index={1: 3, 2: 13, 3: 23}
        command=":Numeric:Normal:VALue? %d" % index[element]
        return float(self._query(command))

    def get_titles(self):
        """Required: returns tuple of titles for first row of CSV file"""
        return self._titles

    def get_values(self):
        """Required: returns tuple of values for rows in CSV file"""
        v=[self.get_power(x) for x in self._elements]
        return tuple(v)

if __name__ == '__main__':
    sampler=Sampler()

    sys.stdout.write("Titles:\n")
    pprint.pprint(sampler.get_titles())

    sys.stdout.write("Values:\n")
    pprint.pprint(sampler.get_values())

