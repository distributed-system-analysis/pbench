#!/usr/bin/env python3

import sys
import os

with open(os.environ["_testlog"], "a") as ofp:
    args = " ".join(sys.argv)
    ofp.write(f"{args}\n")

sys.exit(0)
