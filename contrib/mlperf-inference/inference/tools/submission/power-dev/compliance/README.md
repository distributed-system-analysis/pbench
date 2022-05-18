## Description

The directory contains the compliance checker script that need to be run by the submitter in order to demonstrate a valid submission.
```
usage: check.py [-h] session_directory
```
## Installation

`git clone https://github.com/mlcommons/power-dev`

## Usage Example
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

[2021-03-01_15-59-52_loadgen]: https://github.com/mlcommons/power-dev/files/6116703/2021-03-01_15-59-52_loadgen.zip

## Detailed checks description
### Check client sources checksum and Check server sources checksum
* Compare the current checksum of the code from client.json or server.json against the standard checksum of the source code from sources_checksums.json.

### Check PTD commands and replies
* Check the ptd version number. Supported version 1.9.1 and 1.9.2.
* Check the device type. Supported device types are "YokogawaWT210", "YokogawaWT310", "YokogawaWT330E".
* Compare message replies with expected values.
* Check that initial values are set after the test has been completed.

### Check UUID
* Compare UUIDs from client.json and server.json. They should be the same.

### Check session name
* Check that session names from client.json and server.json are equal.

### Check time difference
* Check that the time difference between corresponding checkpoint values from client.json and server.json is less than 200 ms.
* Check that the loadgen timestamps are within workload time interval.
* Check that the duration of loadgen test for the ranging mode is comparable with duration of loadgen test for the testing mode.

### Check client server messages
* Compare client and server messages list length.
* Compare messages values and replies from client.json and server.json.
* Compare client and server version.

### Check results checksum
* Calculate the checksum for result files. Compare them with the checksums list formed from joined results from server.json and client.json.
* Check that results from client.json and server.json have no extra and absent files.
* Compare that results files from client.json and server.json have the same checksum.

### Check errors and warnings from PTD logs
* Check if ptd message starts with 'WARNING' or 'ERROR' in ptd logs. If errors or warnings messages are "Uncertainty unknown for the last measurement sample!" or "Uncertainty unknown for the last measurement sample!" and they appeared while ranging mode they will be skipped.
* Check 'Uncertainty checking for Yokogawa... is activated' in PTD logs.

### Check PTD configuration
* Check the device number is supported. Supported devices numbers are 8,49,52,77.
* If the device is multichannel, check that two numbers are using for channel configuration.

### Check debug is disabled on server-side


