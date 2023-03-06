#!/bin/bash
# An example of how to run a simple workload with `pbench-user-benchmark`

# In a containerized environment, the Pbench Agent profile must be run to
# establish the proper execution environment.
source /opt/pbench-agent/profile

# The set of tools the user desires to run must be registered before the
# workload is executed.
echo "Registering the 'heavy' tool set provided by the Pbench Agent"
pbench-register-tool-set heavy

# The `user-benchmark` workload wrapper simply takes a configuration name, in
# this case the very generic `example-workload`, followed by the command to use
# to run the workload.  Note that the command is separated by `--` to avoid
# any workload command line arguments that follow from being interpreted as
# options to `pbench-user-benchmark` command itself.
echo "Executing pbench-user-benchmark ..."
pbench-user-benchmark --config example-workload -- fio --directory=/fiotest --name fio_test_file --direct=1 --rw=randread --bs=16k --size=100M --numjobs=16 --time_based --runtime=20s --group_reporting --norandommap
