#!/usr/bin/env python3

import sys
import json
import collections


def main(args):
    # File containing pbench results and run data
    filename = args[1]

    records = []
    for line in open(filename, "r"):
        records.append(json.loads(line))

    sos_and_runids = dict()

    for result in records:
        if (
            result["run.id"] not in sos_and_runids.keys()
        ):  # and len(data[resid]["hostnames"]) == 1:
            sos_and_runids[result["run.id"]] = {
                "sosreports": result["sosreports"],
                "sample.client_hostname": result["sample.client_hostname"],
                "disknames": result["disknames"],
                "controller_dir": result["controller_dir"],
                "run.name": result["run.name"],
            }

    # count sosreports associated with each run
    count = []
    for id in sos_and_runids:
        count.append(len(sos_and_runids[id]["sosreports"].keys()))

    counter = collections.Counter(count)
    print(counter)

    with open("sos_and_runids.json", "w") as outfile:
        json.dump(sos_and_runids, outfile)

    return 0


# point of entry
if __name__ == "__main__":
    status = main(sys.argv)
