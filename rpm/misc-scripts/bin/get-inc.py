#! /usr/bin/env python3

import sys

seqno = int(open(sys.argv[1]).read())
with open(sys.argv[1], "w") as f:
    f.write(str(seqno+1))
    f.write('\n')
print(seqno)
