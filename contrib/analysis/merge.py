#!/usr/bin/env python3

import sys
import json
import pandas as pd


def main(args):
    # File containing pbench results and run data
    pbench_fio = args[1]

    # File containing configuration data
    config_data = args[2]

    pbench_records = []
    for line in open(pbench_fio, "r"):
        pbench_records.append(json.loads(line))

    config_df = pd.read_csv(config_data, delimiter=";", index_col=0)
    config_dict = config_df.to_dict("index")

    pbench = dict()

    index = 1
    for result in pbench_records:
        del result["sosreports"]
        for runid in config_dict:
            # second condition elimintes runs/results with error in fio-result.txt
            if result["run.id"] == runid and result["disknames"]:
                pbench[index] = result
                pbench[index].update(config_dict[runid])
                index = index + 1

    # Form individual dataframes for different results using the dictionary
    df = pd.DataFrame(pbench.values(), index=pbench.keys())
    slat_df = df[df["sample.measurement_title"] == "slat"]
    clat_df = df[df["sample.measurement_title"] == "clat"]
    lat_df = df[df["sample.measurement_title"] == "lat"]
    thr_df = df[df["sample.measurement_type"] == "throughput"]

    # Covert dataframes to csv files
    slat_df.to_csv(r"latency_slat.csv", sep=";", mode="w")
    clat_df.to_csv(r"latency_clat.csv", sep=";", mode="w")
    lat_df.to_csv(r"latency_lat.csv", sep=";", mode="w")
    thr_df.to_csv(r"throughput_iops_sec.csv", sep=";", mode="w")

    return 0


# point of entry
if __name__ == "__main__":
    status = main(sys.argv)
