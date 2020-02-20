#!/usr/bin/env python3

import os
import sys
import shutil

_prog = os.path.basename(sys.argv[0])

if len(sys.argv) < 2:
    print("{}: Missing working directory argument".format(_prog),
          file=sys.stderr)
    sys.exit(1)

if len(sys.argv) > 2:
    print("{}: Too many arguments ({!r})".format(_prog, sys.argv),
          file=sys.stderr)
    sys.exit(1)

try:
    os.chdir(sys.argv[1])
except Exception as e:
    print("{}: {}".format(_prog, e), file=sys.stderr)
    sys.exit(1)

errors = 0
for tar in sys.stdin:
    try:
        src = tar.strip('\n')
        des = src.replace("TO-SYNC", "TO-DELETE")
        shutil.move(src, des)
    except Exception as e:
        errors += 1
        print("{}: {}".format(_prog, e), file=sys.stderr)
        continue

sys.exit(1 if errors > 0 else 0)
