#!/bin/bash

# A demonstration of how to use pbench-tool-meister-start with an existing
# Redis server, and one or more remote

DISTRO="${1}"; shift
TAG="${1}"; shift

if [[ -z "${DISTRO}" ]]; then
    echo "ERROR - Missing 1st argument, the distro target." >&2
    exit 1
fi
if [[ -z "${TAG}" ]]; then
    echo "ERROR - Missing 2nd argument, the image tag." >&2
    exit 1
fi

export REDIS_HOST=${1}; shift
if [[ -z "${REDIS_HOST}" ]]; then
    echo "ERROR - Missing 3rd argument, the Redis server host." >&2
    exit 1
fi
export REDIS_PORT=6379
export PBENCH_REDIS_SERVER="${REDIS_HOST}:${REDIS_PORT}"

export TDS=${1}; shift
if [[ -z "${TDS}" ]]; then
    echo "ERROR - Missing 4th argument, the Tool Data Sink host." >&2
    exit 1
fi

# The remaining arguments will be the Tool Meister hosts.

export pbench_run=$(pwd)/run-dir
rm -rf ${pbench_run}
mkdir ${pbench_run}
#printf -- "${pbench_run}\n" > ${pbench_run}/.path
cp -a ./demo-01-run-pbench.sh ${pbench_run}/
export pbench_log=${pbench_run}/pbench.log

for i in ${*}; do
    echo ${i}
done > ${pbench_run}/remotes.lis

if [[ ! -s ${pbench_run}/remotes.lis ]]; then
    echo "ERROR - We need at least one host to register tools." >&2
    exit 1
fi

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

printf -- "\n\nWe've created a non-root owned pbench run directory:\n\n"

find ${pbench_run} -ls

printf -- "\n\nNotice that it is owned by ${USER} (and we've set the 'pbench_run' ENV to that directory).\n\n"

wait_keypress 120

# Start Tool Meister containers on remote hosts

printf -- "\n\nNow let's start the three Tool Meister pods running on the given hosts...\n\n\t$ podman run --name pbench-agent-tool-meister --network host --ulimit nofile=65536:65536 --rm -d -e REDIS_HOST=${REDIS_HOST} -e REDIS_PORT=${REDIS_PORT} -e PARAM_KEY=tm-default-\$(hostname -f) -e _PBENCH_TOOL_MEISTER_LOG_LEVEL=debug quay.io/pbench/pbench-agent-tool-meister-${DISTRO}:${TAG}\n\n"

wait_keypress 120


# Start the Tool Data Sink locally, mapping our volume into the Tool Data Sink
# container.

printf -- "\n\nNow let's start the local Tool Data Sink to pull tool data into our local volume.\n\n"

printf -- "podman run --name pbench-agent-tool-data-sink --network host --volume ${pbench_run}:/var/lib/pbench-agent:z --ulimit nofile=65536:65536 --rm -d -e REDIS_HOST=${REDIS_HOST} -e REDIS_PORT=${REDIS_PORT} -e PARAM_KEY=tds-default -e _PBENCH_TOOL_DATA_SINK_LOG_LEVEL=debug quay.io/pbench/pbench-agent-tool-data-sink-${DISTRO}:${TAG}\n\n"

printf -- "\n\nNow let's look at the 'podman logs' output from these containers;\n\tnotice we did not start a Redis server yet,\n\tthey'll just be waiting for it to show up.\n\n"

wait_keypress 120


printf -- "\n\nStart the Redis server on ${REDIS_HOST}:${REDIS_PORT}\n\t$ podman run --name demo-tm-redis --network host --rm -d docker.io/library/redis:latest\n\n\tNote TDS and TMs notice Redis server,\n\tbut now wait for their 'PARAM_KEY' to show up.\n\n"

wait_keypress 120


podman run -it --rm --network host --volume ${pbench_run}:/var/lib/pbench-agent:z quay.io/pbench/pbench-agent-base-${DISTRO}:${TAG} /bin/bash

exit 0
