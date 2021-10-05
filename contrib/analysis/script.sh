#!/bin/bash

# Steps to collect Pbench fio data.

es_host=$1
es_port=$2
url_prefix=$3
sos_host=$4

# 1) The following code collects Pbench runs data and Pbench results data from Elasticsearch for the past one year. Pbench runs data gives us the mapping between runs and configuration data. Pbench results data gives us the performance results and workload metadata. The code generates two output files: "pbench_fio.json" and "sosreport_fio.txt". The first file contains complete information about a pbench run with sosreport names but missing configuration data. The second file contains the sosreport names to be copied from the production server. The code also extracts the disk name from fio-result.txt located in each individual sample (can only be accessed using a URL).

./merge_sos_and_perf_parallel.py 1 $es_host $es_port $url_prefix;

# 2) "sosreport_fio.txt" contains a list of all the sosreports from the past one year with pbench-fio results. Use the following command to figure out the unique set of sosreports that we should copy from the production server.

sort sosreport_fio.txt | uniq > sos_fio.lis;

# 3) Use the following command to copy all the sosreports listed in "sos_fio.lis" to your system.

mkdir -p ./sosreports;
while read sos; do scp vos@$sos_host:~/VoS/archive/${sos} ./sosreports/; done < sos_fio.lis;

# 4) Use "pbench_fio.json" to generate "sos_and_runids.json" using <create_sos_with_runids.py>. You could modify the code to filter out certain runs. For example, runs with multiple clients.  

./create_sos_with_runids.py pbench_fio.json;

# 5) Run <collect_config_data.py> that takes in the directory "sosreports", "sos_and_runids.json" and the hostname to collect block parameters. It generates "config.csv" that contains configuration data.

./collect_config_data.py sosreports/ sos_and_runids.json $url_prefix;

# 6) To merge the information from sosreports, workload metadata and performance results, use <merge.py>. It takes in "config.csv" and "pbench_fio.json" and generates four files: "latency_slat.csv", "latency_clat.csv", "latency_lat.csv" and "throughput_iops_sec.csv".

./merge.py pbench_fio.json config.csv;
