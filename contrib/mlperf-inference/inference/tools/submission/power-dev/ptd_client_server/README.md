## Description

This client-server application is intended to measure the power consumed during the execution of the specified workload.

The server is intended to be run on the director (the machine on which PTDaemon runs),
and the client is intended to be run on the SUT (system under test).

The client accepts a shell command to run, i.e. the workload.
The power is measured by the server during the command execution on a client.

The command is run twice for each setting: the first time in ranging mode, and the second time is in testing mode.

Client-server sequence diagram: [sequence.png](./doc/sequence.png)

## Prerequisites

* Python 3.7 or newer
* Supported OS: Windows or Linux
* PTDaemon (on the server)
* On Linux: `ntpdate`, optional (see below).
* On Windows: install `pywin32` python dependency (see below).
* Assuming you are able to run the required [inference] submission.
  In the README we use [ssd-mobilenet] as an example.

[inference]: https://github.com/mlcommons/inference
[ssd-mobilenet]: https://github.com/mlcommons/inference/tree/master/vision/classification_and_detection

### NTP

To make sure the Loadgen logs and PTDaemon logs match, the system time should be synchronized on the client and the server.
Both the client and the server have an option to configure the NTP server address to sync with before running a workload.

There are two options:

1. Sync the system time by yourself.
  You still need to specify NTP server both for the client and the server for the verification.

2. Let the script sync the system time.
  Runs automatically if the verification fails.

For the second option, you need to have the following prerequisites.

#### On Linux

1. Install `ntpdate` binary. Ubuntu package: `ntpdate`.
2. Disable pre-existing NTP daemons if they are running.
   On Ubuntu: `systemctl disable systemd-timesyncd; systemctl stop systemd-timesyncd; systemctl disable ntp; systemctl stop ntp`.
3. Root privileges are required. Either run the script as root or set up a passwordless `sudo`.

#### On Windows
1. Install `pywin32`: `python -m pip install pywin32`.
2. Disable default Windows Time Service (`w32tm`).
3. Run the script as an administrator.

## Installation

`git clone https://github.com/mlcommons/power`

or

`pip install git+https://github.com/mlcommons/power-dev`

(also see INSTALL.md).

## Configuration

The server requires the configuration file to be passed using the `-c` command line argument.
A template of this file is provided below and in the [`server.template.conf`](./server.template.conf) file.

```ini
# Server Configuration Template
# To use change the section of the config that you'd like to change.

[server]
# NTP server to sync with before each measurement.
# See "NTP" section in the README.md.
#ntpServer: ntp.example.com

# A directory to store output data. A relative or absolute path could be used.
# A new subdirectory will be created per each run.
# The name of this sub-directory consists of date, time, label, and mode (ranging/testing).
# The loadgen log is fetched from the client if the `--send-logs` option is enabled for the client.
# The name of the directory is determined by the workload script running on the SUT, e.g. `ssdmobilenet`.
# The power log, named `spl.txt`, is extracted from the full PTDaemon log (`ptdLogfile`)
outDir: D:\ptd-logs\

# (Optional) IP address and port that server listen on
# Defaults to "0.0.0.0 4950" if not set
#listen: 192.168.1.2 4950


# PTDaemon configuration.
# The following options are mapped to PTDaemon command line arguments.
# Please refer to SPEC PTDaemon Programmers Guide or `ptd -h` for the details.
[ptd]
# A path to PTDaemon executable binary.
ptd: D:\PTD\ptd-windows-x86.exe

# A path to a logfile that PTDaemon produces (`-l` option).
# Note that in the current implementation this file is considered temporary
# and may be overwritten.
logFile: logs_ptdeamon.txt

# (Optional) A port on that PTDaemon listens (`-p` option). Default is 8888.
#networkPort: 8888

# Power Analyzer numerical device type. Refer to `ptd -h` for the full list.
# 49 corresponds to Yokogawa WT310.
deviceType: 49

# interfaceFlag and devicePort describe the physical connection to the analyzer.
# interfaceFlag is either one of -n, -g, -y, -U, or empty.
# Refer to SPEC PTDaemon Programmers Guide or `ptd -h` for the details.
# Below are some examples of interfaceFlag and devicePort pairs.

# Use RS232 interface.
# Empty interfaceFlag corresponds to RS232.
interfaceFlag:
devicePort: COM1

# Use GPIB interface.
#interfaceFlag: -g
#devicePort: 0

# Set GPIB board number (`-b` option)
#gpibBoard: 0

# Use TCPIPv4 ethernet interface.
#interfaceFlag: -n
#devicePort: 192.168.1.123

# Use Yokogawa TMCTL for USB or ethernet interface.
# devicePort should be either the IP address or device serial number.
#interfaceFlag: -y
#devicePort: C2PH13047V

# (Optional) Channel number for multichannel analyzers operating in single channel mode. (`-c` option)
# Channel value should consist of two numbers separated by a comma for a multichannel analyzer.
# Channel value should consist of one number or be disabled for a 1-channel analyzer.
#channel: 1,2
```

Client command line arguments:

```
usage: client.py [-h] -a ADDR -w CMD -L INDIR -o OUTDIR -n ADDR [-p PORT] [-l LABEL] [-s] [-f] [-S]

PTD client

required arguments:
  -a ADDR, --addr ADDR            server address
  -w CMD, --run-workload CMD      a shell command to run under power measurement
  -L INDIR, --loadgen-logs INDIR  collect loadgen logs from INDIR
  -o OUTDIR, --output OUTDIR      put logs into OUTDIR (copied from INDIR)
  -n ADDR, --ntp ADDR             NTP server address

optional arguments:
  -h, --help                      show this help message and exit
  -p PORT, --port PORT            server port, defaults to 4950
  -l LABEL, --label LABEL         a label to include into the resulting directory name
  -s, --send-logs                 send loadgen logs to the server
  -F, --fetch-logs                fetch logs from the server
  -f, --force                     force remove loadgen logs directory (INDIR)
  -S, --stop-server               stop the server after processing this client
```

* `INDIR` is a directory to get loadgen logs from.
  The workload command should place inside this directory.

* `LABEL` is a human-readable label.
  The label is used later both on the client and the server to distinguish between log directories.

* If `-s`/`--send-logs` is enabled, then the loadgen log will be sent to the server and stored alongside the power log.

## Usage Example

In these examples we have the following assumptions:
* The director IP address is 192.168.1.2.
* The current repository is cloned to `/path/to/mlcommons/power`.
* Using `ntp.example.com` as an NTP server.

Start a server (on a director):
```sh
./server.py -c server-config.conf
```
or (if installed with pip):
```sh
power_server -c server-config.conf
```

Then on the SUT, provide a workload script for your particular workload and run it using `client.py`
(or `power_client` if installed with pip).
Choose an option below for the example of workload script.

<details><summary>Example option 1: a dummy workload</summary>

Create a dummy workload script named `dummy.sh`.
It does nothing but mimicking the real loadgen by creating empty loadgen log files in the `dummy-loadgen-logs` directory.

```sh
#!/usr/bin/env bash

sleep 5
mkdir -p dummy-loadgen-logs

# Create empty files with the same names as loadgen do

touch dummy-loadgen-logs/mlperf_log_accuracy.json
touch dummy-loadgen-logs/mlperf_log_detail.txt
touch dummy-loadgen-logs/mlperf_log_summary.txt
touch dummy-loadgen-logs/mlperf_log_trace.json
```
Don't forget to `chmod +x dummy.sh`.

Then start a client using `./dummy.sh` as a workload being measured.
Pass `dummy-loadgen-logs` as a location of loadgen logs.

```sh
/path/to/mlcommons/power/ptd_client_server/client.py \
    --addr 192.168.1.2 \
    --output "client-output-directory" \
    --run-workload "./dummy.sh"
    --loadgen-logs "dummy-loadgen-logs" \
    --label "mylabel" \
    --send-logs \
    --ntp ntp.example.com
```

</details>

<details><summary>Example option 2: loadgen benchmark</summary>

Source: https://github.com/mlcommons/inference/tree/master/loadgen/benchmark

Use the following script to build loadgen benchmark:
```sh
#!/usr/bin/env bash

echo "Building loadgen..."
if [ ! -e loadgen_build ]; then mkdir loadgen_build; fi;
cd loadgen_build && cmake ../.. && make -j && cd ..
echo "Building test program..."
if [ ! -e build ]; then mkdir build; fi;
g++ --std=c++11 -O3 -I.. -o repro.exe repro.cpp -Lloadgen_build -lmlperf_loadgen -lpthread
```

Create `run_workload.sh`:
```sh
#!/usr/bin/env bash

if [ ! -e build ]; then mkdir build; fi;
./repro.exe 800000 0 4 2048
```

Don't forget to `chmod +x run_workload.sh`.

Then start a client using `./run_workload.sh` as a workload being measured.
The benchmark is hardcoded to put its logs into the `build` directory, so we specify it as a loadgen log location.
Run it from the same directory (`loadgen/benchmark`).

```sh
/path/to/mlcommons/power/ptd_client_server/client.py \
    --addr 192.168.1.2 \
    --output "client-output-directory" \
    --run-workload "./run_workload.sh" \
    --loadgen-logs "build" \
    --label "mylabel" \
    --send-logs \
    --ntp ntp.example.com
```

</details>

<details><summary>Example option 3: ssd-mobilenet</summary>

Source: https://github.com/mlcommons/inference/tree/master/vision/classification_and_detection

First, follow the instructions in the link above to build and run the `ssd-mobilenet` inference benchmark.
You'll also need to download the corresponding model and datasets.

Then, use the following script to run the benchmark under the power measurement.
It uses `./run_local.sh` as the workload script.
The workload script stores its output in the directory `./output/tf-cpu/ssd-mobilenet`.

```sh
#!/usr/bin/env bash

# Don't forget to update the following paths
export MODEL_DIR=/path/to/model/dir
export DATA_DIR=/path/to/data/dir
cd /path/to/mlcommons/inference/vision/classification_and_detection

/path/to/mlcommons/power/ptd_client_server/client.py \
	--addr 192.168.1.2 \
	--output "client-output-directory" \
	--run-workload "./run_local.sh tf ssd-mobilenet cpu --scenario Offline" \
	--loadgen-logs "./output/tf-cpu/ssd-mobilenet" \
	--label "mylabel" \
	--send-logs \
	--ntp ntp.example.com
```

</details>

All the options above store their output in the `client-output-directory` directory, but you can specify any other directory.

After a successful run, you'll see these new files and directories on the server:

```
D:\ptd-logs
├── … (old entries skipped)
└── 2020-12-28_15-20-52_mylabel
    ├── power
    │   ├── client.json                  ← client summary
    │   ├── client.log                   ← client stdout log
    │   ├── ptd_logs.txt                 ← ptdaemon stdout log
    │   ├── server.json                  ← server summary
    │   └── server.log                   ← server stdout log
    ├── ranging
    │   ├── mlperf_log_accuracy.json   ┐ ← loadgen log, if --send-logs is used.
    │   ├── mlperf_log_detail.txt      │   Produced by the workload script on
    │   ├── mlperf_log_summary.txt     │   the client.
    │   ├── mlperf_log_trace.json      ┘
    │   └── spl.txt                      ← power log
    └── run_1
        ├── mlperf_log_accuracy.json   ┐
        ├── mlperf_log_detail.txt      │ ← loadgen log (same as above)
        ├── mlperf_log_summary.txt     │
        ├── mlperf_log_trace.json      ┘
        └── spl.txt                      ← power log
```

And these on the SUT:

```
./client-output-directory
├── … (old entries skipped)
└── 2020-12-28_15-20-52_mylabel_ranging
    ├── client.json
    ├── client.log
    ├── ranging
    │   ├── mlperf_log_accuracy.json   ┐
    │   ├── mlperf_log_detail.txt      │ ← loadgen log
    │   ├── mlperf_log_summary.txt     │
    │   └── mlperf_log_trace.json      ┘
    └── testing
        ├── mlperf_log_accuracy.json   ┐
        ├── mlperf_log_detail.txt      │ ← loadgen log
        ├── mlperf_log_summary.txt     │
        └── mlperf_log_trace.json      ┘
```

`spl.txt` consists of the following lines:
```
Time,28-12-2020 15:21:14.682,Watts,22.950000,Volts,228.570000,Amps,0.206430,PF,0.486400,Mark,2020-12-28_15-20-52_mylabel_testing
Time,28-12-2020 15:21:15.686,Watts,23.080000,Volts,228.440000,Amps,0.207320,PF,0.487400,Mark,2020-12-28_15-20-52_mylabel_testing
Time,28-12-2020 15:21:16.691,Watts,22.990000,Volts,228.520000,Amps,0.206740,PF,0.486500,Mark,2020-12-28_15-20-52_mylabel_testing
```

## Unexpected test termination

During the test, the client and the server maintain a persistent TCP connection.

In the case of unexpected client disconnection, the server terminates the power measurement and consider the test failed.
The client intentionally doesn't perform an attempt to reconnect to make the test strict.

Additionally, [TCP keepalive] is used to detect a stale connection and don't let the server wait indefinitely in case if the client is powered off during the test or the network cable is cut.
Keepalive packets are sent each 2 seconds, and we consider the connection broken after 10 missed keepalive responses.

[TCP keepalive]: https://en.wikipedia.org/wiki/Keepalive#TCP_keepalive
[inference]: https://github.com/mlcommons/inference

## Compliance checks

The directory [compilance] contains the compliance checker script that need to be run by the submitter in order to demonstrate a valid submission.
```
usage: check.py [-h] session_directory
```
Usage example:
```
python .\checker.py D:\ptd-logs\2021-03-01_15-59-52_loadgen
```
The expected structure of D:\ptd-logs\2021-03-01_15-59-52_loadgen is:
```
D:\ptd-logs
├── … (old entries skipped)
└── 2021-03-01_15-59-52_loadgen
    ├── power
    │   ├── client.json
    │   ├── client.log
    │   ├── ptd_logs.txt
    │   ├── server.json
    │   └── server.log
    ├── ranging
    │   ├── mlperf_log_detail.txt
    │   ├── mlperf_log_summary.txt
    │   └── spl.txt
    └── run_1
        ├── mlperf_log_detail.txt
        ├── mlperf_log_summary.txt
        └── spl.txt
```
Directory with results example is [2021-03-01_15-59-52_loadgen].

To get this structure on the server side you should use `--send-logs` option for client.py.
To get this structure on the client side you should use `--fetch-logs` option for client.py.
On other hand, you can get the such files structure manually joined client and server output results.
If everything is fine you see the next messages after check.py run:
```
[x] Check client sources checksum
[x] Check server sources checksum
[x] Check PTD commands and replies
[x] Check UUID
[x] Check session name
[x] Check time difference
[x] Check client server messages
[x] Check results checksum
[x] Check errors and warnings from PTD logs
[x] Check PTD configuration
[x] Check debug is disabled on server-side
```

[compilance]: ../compliance
[2021-03-01_15-59-52_loadgen]: https://github.com/mlcommons/power-dev/files/6116703/2021-03-01_15-59-52_loadgen.zip
