#!/bin/bash

if [[ ! -f ./var_lib_pbench-agent/.token || ! -f ./pbench-agent.cfg.tmp ]]; then
    echo "Please run ./setup.sh to properly setup the required environment." >&2
    exit 1
fi

# Create a `fiotest` directory to use as the target directory of the `fio`
# workload execution.
mkdir -p fiotest

# Run the workload in the container.
#
# The `example-workload.sh` script is mounted into the container as
# `/workload.sh`, along with the target `fiotest` directory it requires, and the
# location of `/var/lib/pbench-agent`.  This example relies on the CentOS 8
# Pbench Agent "all" container image (which has everything and the kitchen sink
# installed).
#
# Notice that host networking is used for the container.
#
# NOTE that the container is not run with any privileges or adjusted namespaces
# so the tool data collected may not be what you expect.
podman run \
    --rm \
    --network host \
    --name example-workload \
    -v ${HOME}/.ssh:/root/.ssh:z \
    -v ./example-workload.sh:/workload.sh:z \
    -v ./var_lib_pbench-agent:/var/lib/pbench-agent:z \
    -v ./fiotest:/fiotest:z \
    quay.io/pbench/pbench-agent-all-centos-8:latest /workload.sh

# Move the results to the target Pbench Server
#
# Note that we run the mover separately to demonstrate that the collected data
# is independent of the containerized environment in which it was collected.
podman run \
    -it \
    --rm \
    --network host \
    -v ./mover.sh:/mover.sh:z \
    -v ./pbench-agent.cfg.tmp:/opt/pbench-agent/config/pbench-agent.cfg:z \
    -v ./var_lib_pbench-agent:/var/lib/pbench-agent:z \
    quay.io/pbench/pbench-agent-all-centos-8:latest /mover.sh
