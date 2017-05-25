#!/usr/bin/env python3

# From DSA/satools/satools/
# https://github.com/distributed-system-analysis/satools

from __future__ import print_function

import os
import sys

try:
    from sysstat import fetch_fileheader, fetch_os_code, Invalid
except:
    from .sysstat import fetch_fileheader, fetch_os_code, Invalid

def determine_version(file_path=None):
    if os.path.getsize(file_path) == 0:
        return (False, "Invalid - %s: empty data file" % file_path)

    try:
        fm, fh, fa, magic = fetch_fileheader(file_path)
    except Invalid as e:
        return (False, "Invalid - %s: %s" % (file_path, e))

    except Exception as e:
        return (False, "Error - %s: %s" % (file_path, e))


    try:
        val = fetch_os_code(magic)
    except Invalid as e:
        return (False, "Invalid - %s: %s" % (file_path, e))

    except Exception as e:
        return (False, "Error - %s: %s" % (file_path, e))

    else:
        return (True, val)

if __name__ == '__main__':
    res = determine_version(file_path=sys.argv[1])
    if res[0]:
        print(res[1])
    else:
        print(res[1], file=sys.stderr)
        sys.exit(1)
