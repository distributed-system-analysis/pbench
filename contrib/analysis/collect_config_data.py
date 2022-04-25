#!/usr/bin/env python3

import os
import sys
import json
import time
import requests
import tarfile
import pandas as pd
import logging
import multiprocessing


def _strip(o):
    return o.strip()


def decode_bytes(inbytes):
    try:
        unibytes = inbytes.decode("utf-8")
    except UnicodeDecodeError:
        unibytes = inbytes.decode("iso8859-1")
    return unibytes


# collect data from the lscpu file
def collect_lsblk(fobj):
    data = dict()
    lsblk_disks = []
    for line in decode_bytes(fobj.read()).splitlines()[1:]:
        parts = list(map(_strip, line.split(" ", 1)))
        if parts[0] and parts[0][0].isalpha():
           lsblk_disks.append(parts[0])
    data['lsblk_disks'] = lsblk_disks
    return data


# collect data from the lsblk file
def collect_lscpu(fobj):
    data = dict()
    physical = "True"
    for line in decode_bytes(fobj.read()).splitlines():
        parts = list(map(_strip, line.split(":", 1)))
        featurename = parts[0].replace(" ", "_")
        if featurename in ["Architecture", "Model_name"]:
            data[featurename] = parts[1]
        elif featurename in [
            "CPU(s)",
            "Core(s)_per_socket",
            "Socket(s)",
            "Thread(s)_per_core",
            "NUMA_node(s)"   # recommended by Peter
        ]:
            data[featurename] = int(parts[1])
        elif featurename in [
            "L1d_cache",
            "L1i_cache",
            "L2_cache",
            "L3_cache"
        ]:
            if "KiB" in parts[1]:
                data[featurename] = int(parts[1][:-4])
            elif "MiB" in parts[1]:
                data[featurename] = int(parts[1][:-4])*1000
            elif "M" in parts[1]:
                data[featurename] = int(parts[1][:-1])*1000 # do not include M for megabytes
            else:
                data[featurename] = int(parts[1][:-1]) # do not include K for kilobytes
        elif featurename == "Hypervisor_vendor":
            physical = False
    if physical:
        data['Type'] = 'phy'
    else:
        data['Type'] = 'virt'
    return data


# collect data from the meminfo file
def collect_meminfo(fobj):
    data = dict()
    for line in decode_bytes(fobj.read()).splitlines():
        parts = list(map(_strip, line.split(":", 1)))
        featurename = parts[0].replace(" ", "_")
        if featurename == "MemTotal":
            data[featurename] = int(parts[1][:-3])  # do not include kB
    return data


# collect system uuid from the dmidecode command output
def collect_uuid(fobj):
    data = dict()
    blocks = decode_bytes(fobj.read()).split("\n\n")
    for block in blocks[:-1]:
        if block.splitlines()[1] == "System Information":
            for line in block.splitlines()[2:]: # ignore first two lines
                parts = list(map(_strip, line.split(':', 1)))
                if parts[0] == 'UUID':
                    data['UUID'] = parts[1]
                    break
    return data


# collect kernel version from the uname_-a command output
def collect_kernel_version(fobj):
    data = dict()
    line = decode_bytes(fobj.read())
    parts = list(map(_strip, line.split()))
    data["Static_hostname"] = parts[1]
    data["Kernel"] = parts[0] + " " + parts[2]
    return data


# collect data from all the files with a single integer value
def collect_single_value(fobj):
    data = int(decode_bytes(fobj.read()))
    return data


# collect active tuned profile
def collect_tuned_profile(fobj):
    data = decode_bytes(fobj.read())
    return data


# collect scheduler type from the disk parameters
def collect_scheduler(fobj):
    data = dict()
    scheduler = "Missing"
    line = decode_bytes(fobj.read())
    parts = list(map(_strip, line.split()))
    for part in parts:
        if part[0] == '[' and part[-1] == ']':
            scheduler = part[1:-1]
    data["scheduler"] = scheduler
    return data


# extract block parameters from block-params.log
def extract_block_params(url, filenames):
    data = dict()
    # check if the page is accessible
    r = requests.head(url, allow_redirects=True)
    if r.status_code == 200: # successful
        page = requests.get(url)
        for line in page.iter_lines():
            for name in filenames:
                if name in line.decode():
                    parts = list(map(_strip, (line.decode()).split()))
                    head, tail = os.path.split(parts[0])
                    if tail == 'scheduler':
                        data[tail] = parts[1]
                    else:
                        data[tail] = int(parts[1])    
    return data


def collect_sosreport_data(rootdir, dirname, filenames, sos_with_runids, url_prefix):
    record = dict()  # data from one sosreport
    filesread = 0

    # find the run id associated with the sosreport
    for id in sos_with_runids:
        if dirname in sos_with_runids[id]['sosreports'].keys():
            run_id = id
            time = sos_with_runids[id]['sosreports'][dirname]['time']
            host = sos_with_runids[id]['sample.client_hostname']
            shorthost = sos_with_runids[id]['sosreports'][dirname]['hostname-s']
            disknames = sos_with_runids[id]['disknames']
            controller_dir = sos_with_runids[id]['controller_dir']
            runname = sos_with_runids[id]['run.name']

    # check if run_id is set, otherwise no need to process the sosreport
    if 'run_id' not in locals(): 
        return dict()      

    try:
        with tarfile.open(os.path.join(rootdir, dirname)) as tar:

            # store the run.id and sosreport name in the record
            record['run_id'] = run_id
            record['sosreport'] = dirname
            record['time'] = time
            record['host'] = host

            for member in tar.getmembers():
                parts = (member.name).split("/")
                filename = "/".join(parts[1:])
                if filename in filenames:
		    
                    f = tar.extractfile(member)

                    # check if all the files needed exist and are not empty
                    if f is None or member.size == 0:
                        isvalid = False
                        sys.stderr.write(
                            "Error: Invalid sosreport:"
                            f" {dirname}:{parts[-1]}"
                            " file not found or is empty.\n")
                        continue
                    if parts[-1] == "meminfo":
                        record.update(collect_meminfo(f))
                    elif parts[-1] == "lscpu":
                        record.update(collect_lscpu(f))
                    elif parts[-1] == "lsblk":
                        record.update(collect_lsblk(f))
                        if len(record["lsblk_disks"]) == 1:
                            record['disk'] = record["lsblk_disks"][0]
                        elif len(list(set(disknames))) == 1 and \
                            disknames[0] in record["lsblk_disks"]:
                            record['disk'] = disknames[0]
                        if 'disk' not in record.keys():
                            record['disk'] = 'Missing'
                        else:
                            # replace sdX in filenames with the disk used
                            for index, name in enumerate(filenames):
                                filenames[index] = name.replace("sdX", record['disk'])
                        record['lsblk_disks'] = ','.join(record['lsblk_disks'])
                    elif parts[-1] == "uname_-a":
                        record.update(collect_kernel_version(f))
                    elif parts[-1] == "scheduler":
                        record.update(collect_scheduler(f))
                    elif parts[-1] == "active_profile":
                        record["active_profile"] = collect_tuned_profile(f)
                    else:
                        record[parts[-1]] = collect_single_value(f)
                    filesread += 1
    except Exception:
        logger.exception("Error working with sosreport %s", dirname)
 
    # for cases where lsblk is empty or missing
    if 'disk' not in record.keys():
        return dict()

    # Extract block parameters 
    url = f"{url_prefix}/incoming/{controller_dir}/{runname}/sysinfo/end/{shorthost}/block-params.log" 
    diskparams = extract_block_params(url, filenames)
    record.update(diskparams)
    filesread += len(diskparams)

    return record


def main(args, logger):
    # Directory with sosreports
    rootdir = args[1]  

    # Mapping between runs and sosreports
    with open(args[2]) as json_file: 
        sos_with_runids = json.load(json_file)  
 
    # URL prefix to fetch unpacked data
    url_prefix = args[3]

    filenames = [
        "proc/meminfo",
        "sos_commands/processor/lscpu",
        "proc/sys/kernel/sched_rr_timeslice_ms",
        "proc/sys/vm/nr_hugepages",
        "proc/sys/vm/nr_overcommit_hugepages",
        "proc/sys/vm/overcommit_memory",
        "proc/sys/vm/dirty_ratio",
        "proc/sys/vm/dirty_background_ratio",
        "proc/sys/vm/overcommit_ratio",
        "proc/sys/vm/max_map_count",
        "proc/sys/vm/min_free_kbytes",
        "proc/sys/vm/swappiness",
        "proc/sys/fs/aio-max-nr",
        "proc/sys/fs/file-max",
        "proc/sys/kernel/msgmax",
        "proc/sys/kernel/msgmnb",
        "proc/sys/kernel/msgmni",
        "proc/sys/kernel/shmall",
        "proc/sys/kernel/shmmax",
        "proc/sys/kernel/shmmni",
        "proc/sys/kernel/threads-max",
        "sos_commands/kernel/uname_-a",
        "sos_commands/block/lsblk",
        "sys/block/sdX/queue/add_random",
        "sys/block/sdX/queue/iostats",
        "sys/block/sdX/queue/max_sectors_kb",
        "sys/block/sdX/queue/nomerges",
        "sys/block/sdX/queue/nr_requests",
        "sys/block/sdX/queue/optimal_io_size",
        "sys/block/sdX/queue/read_ahead_kb",
        "sys/block/sdX/queue/rotational",
        "sys/block/sdX/queue/rq_affinity",
        "sys/block/sdX/queue/scheduler",
        "etc/tuned/active_profile" # recommended by Peter
    ]

    # stores output from all the sosreports 
    result_list = []

    scan_start = time.time()
    pool = multiprocessing.Pool(multiprocessing.cpu_count()-1 or 1) # no. of processes to run in parellel

    scan_count = 0
    for direntry in os.scandir(rootdir):
        if direntry.name.endswith(".md5"):
            continue
        #print(direntry.name)
        scan_count += 1
        result_list.append(pool.apply_async(collect_sosreport_data, 
                                            args=(rootdir, direntry.name, filenames, sos_with_runids, url_prefix, )))

    pool.close()  # no more parallel work to submit
    pool.join()   # wait for the worker processes to terminate

    database = dict()  # stores config data for all the pbench runs

    for res in result_list: 
        record = res.get()
        if record:
            run_id = record['run_id']
            record.pop('run_id', None)

            # Use config data only from sosreports collected at the 'end' of a run
            if run_id not in database.keys() and \
               record['time'] == 'end' and \
               record['Static_hostname'] in record['host']: # since -1 might be appended at the end of record[host]
                database[run_id] = record
    
    print ("Total records: " + str(len(database)))

    # Find pbench runs for which we do not have sosreport information available
    for id in sos_with_runids:
        if id not in database.keys():
            print (sos_with_runids[id])
 
    scan_end = time.time()
    duration = scan_end - scan_start
    scan_rate = duration / scan_count if scan_count > 0 else 0
    print(
        f"--- sosreport scan took {duration:0.2f} seconds"
        f" for {scan_count} sosreports ({scan_rate:0.2f} secs per rpt) ---"
    )

    # Exit if none of the sosreports is valid and the database is empty
    if not database:
        sys.stdout.write("None of the sosreports are valid.\nExiting now...\n")
        return 0

    # Form a dataframe using the data collected from all the files
    df = pd.DataFrame(database.values(), index=database.keys())

    # Print number of uniqe values for each feature
    print(df.nunique())

    # Covert dataframe to a csv file
    df.to_csv(r"config.csv", sep=";", mode="a")

    return 0


# point of entry
if __name__ == "__main__":
    logger = logging.getLogger(os.path.basename(sys.argv[0]))
    start_time = time.time()
    status = main(sys.argv, logger)
    duration = time.time() - start_time
    print(f"--- {duration:0.2f} seconds ---")
    sys.exit(status)
