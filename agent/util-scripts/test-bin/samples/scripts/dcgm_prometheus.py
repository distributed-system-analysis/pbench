#!/usr/bin/env python2

import os
import sys
import time

with open(os.environ["_testlog"], "a") as ofp:
    args = " ".join(sys.argv)
    ofp.write("%s\n" % (args,))

with open("dcgm.file", "a+") as ofp:
    args = " ".join(sys.argv)
    ofp.write("%s\n" % (args,))

time.sleep(9999)

sys.exit(0)
