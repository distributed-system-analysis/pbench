#!/usr/bin/env python3

import sys
import os

with open(os.environ["_testlog"], "a") as ofp:
    args = " ".join(sys.argv)
    ofp.write(f"{args}\n")

val = os.environ.get("_PBENCH_UNIT_TESTS_NO_MATCH_BINARY_SEARCH", "")
if os.environ.get("_PBENCH_UNIT_TESTS_NO_MATCH_BINARY_SEARCH", ""):
    bad_msg = "something other than a "
else:
    bad_msg = val

print(f"Starting {bad_msg}binary-search")
if not os.environ.get("_PBENCH_UNIT_TESTS_UNFINISHED_BINARY_SEARCH", ""):
    print(f"Finished {bad_msg}binary-search")

sys.exit(int(os.environ.get("_PBENCH_UNIT_TESTS_BINARY_SEARCH_EXIT_CODE", "0")))
