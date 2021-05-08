#!/bin/bash

# A demonstration of how to use pbench-tool-meister-start with an existing
# Redis server, and one or more remote

DISTRO="fedora-33"
TAG="87b72256e"
export REDIS_HOST=192.168.182.128
export REDIS_PORT=6379
export PBENCH_REDIS_SERVER="${REDIS_HOST}:${REDIS_PORT}"

function wait_keypress {
    echo "Press any key to continue"
    while [[ true ]]; do
        read -t ${1} -n 1
        if [[ ${?} = 0 ]]; then
            return 0
        else
            echo "waiting for the keypress"
        fi
    done
}

clear

printf -- "++++\n\nDemonstration of the Tool Meister sub-system as non-root, containerized.\n\n----\n\n\n"

printf -- "We are using 5 different hosts for this demonstration\n\n"
printf -- "\t1. 192.168.182.128 - Debian, running the Redis server in a podman container,\n\t\tas my login user, kali\n\t\tNOTE: the pbench-agent RPM is not installed.\n"
printf -- "\t2. 192.168.182.128 - Debian host where I'm running this demonstration\n\t\tscript that will\n\t\t * register tools\n\t\t * collect tool data\n\t\t * performing the above all as **NON-root** user\n\t\tNOTE: the pbench-agent RPM also not installed here, but we'll run from a pbench-agent container.\n"
printf -- "\t3. 192.168.182.1[29:30] - 2 Debian hosts where I'll run three non-root\n\t\tTool Meister containers\n\t\tNOTE: the pbench-agent RPM is not installed.\n\n\n"

wait_keypress 120

# If somebody wants to write their own pbench-tool-meister-start, great, then
# that person can change the assumption on where the persistent volume is for
# the Tool Data Sink, and how the "sysinfo", "init", and "end" commands
# operate with respect to data storage.

export pbench_run=$(pwd)/run-dir
rm -rf ${pbench_run}
mkdir ${pbench_run}
printf -- "${pbench_run}\n" > ${pbench_run}/.path
export pbench_log=${pbench_run}/pbench.log

printf -- "\n\nI've created my non-root pbench run directory:\n\n"

find ${pbench_run} -ls

printf -- "\n\nNotice that it is owned by kali (and I've set the 'pbench_run' ENV to that directory).\n\n"

wait_keypress 120


# Register tools

printf -- "\nNow we'll register five tools that can be run in the Tool Meister containers,\n\n\t'vmstat', 'turbostat', 'sar', 'pcp', and 'node-exporter',\n\n... using a file containing all three remote hosts running the Tool Meister\n(note that 'pcp' and 'node-exporter' are two of the new _persistent_ tools that run\nindependent of the traditional start/stop tools).\n\n"

wait_keypress 120


for i in {28..30}; do
    echo 192.168.182.1${i}
done > ${pbench_run}/remotes.lis

# Register the default tool set, will be recorded in
# ${pbench_run}/tools-v1-default
for tool in vmstat mpstat jaeger; do
    printf -- "\npbench-register-tool --name=${tool} --remotes=@${pbench_run}/remotes.lis\n"
    pbench-register-tool --name=${tool} --remotes=@${pbench_run}/remotes.lis
    sleep 1
done

printf -- "\n\n"
ls -lR ${pbench_run}/tools-v1-default

printf -- "\n\n"
wait_keypress 120


# Start Tool Meister containers on remote hosts

printf -- "\n\nNow let's start the three Tool Meister pods running on the gprfc hosts...\n\n\t$ podman run --name pbench-agent-tool-meister --network host --ulimit nofile=65536:65536 --rm -d -e REDIS_HOST=${REDIS_HOST} -e REDIS_PORT=${REDIS_PORT} -e PARAM_KEY=tm-default-\$(hostname -I | awk '{print \$1}') -e _PBENCH_TOOL_MEISTER_LOG_LEVEL=debug quay.io/pbench/pbench-agent-tool-meister-${DISTRO}:${TAG}\n\n"

wait_keypress 120


# Start the Tool Data Sink locally, mapping our volume into the Tool Data Sink
# container.

printf -- "\n\nNow let's start the local Tool Data Sink to pull tool data into our local volume.\n\n"

set -x
podman run --name pbench-agent-tool-data-sink --network host --volume ${pbench_run}:/var/lib/pbench-agent:Z --ulimit nofile=65536:65536 --rm -d -e REDIS_HOST=${REDIS_HOST} -e REDIS_PORT=${REDIS_PORT} -e PARAM_KEY=tds-default -e _PBENCH_TOOL_DATA_SINK_LOG_LEVEL=debug quay.io/pbench/pbench-agent-tool-data-sink-${DISTRO}:${TAG}
set +x

printf -- "\n\nNow let's look at the 'podman logs' output from these containers;\n\tnotice we did not start a Redis server yet,\n\tthey'll just be waiting for it to show up.\n\n"

wait_keypress 120


printf -- "\n\nStart the Redis server on ${REDIS_HOST}:${REDIS_PORT}\n\t$ podman run --name demo-tm-redis --network host --rm -d docker.io/library/redis:latest\n\n\tNote TDS and TMs notice Redis server,\n\tbut now wait for their 'PARAM_KEY' to show up.\n\n"

set -x
podman run --name redis-server --network host --rm -d docker.io/library/redis:latest
set +x

wait_keypress 120

echo "sleep-iter-0 10" > ${pbench_run}/my-iterations.lis
echo "sleep-iter-11 11" >> ${pbench_run}/my-iterations.lis
echo "sleep-iter-42 12" >> ${pbench_run}/my-iterations.lis
echo "sleep-iter-42 120" >> ${pbench_run}/my-iterations.lis

podman run -it --rm --network host --volume ${pbench_run}:/var/lib/pbench-agent:Z quay.io/pbench/pbench-agent-base-fedora-33:a933ae45e /bin/bash

exit 0

pbench-user-benchmark --config="my-config-001" --iteration-list=${pbench_run}/my-iterations.lis --sysinfo=none -- sleep 10
