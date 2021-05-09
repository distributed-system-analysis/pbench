#!/bin/bash

# Intended to be run inside a pbench-agent container

export PBENCH_ORCHESTRATE=existing
if [[ -z "${1}" ]]; then
    echo "ERROR - Need a Redis server specification." >&2
    exit 1
fi
export PBENCH_REDIS_SERVER=${1}
export PBENCH_TOOL_DATA_SINK=${2:-${PBENCH_REDIS_SERVER}}

export pbench_run=/var/lib/pbench-agent

if [[ ! -f "${pbench_run}/remotes.lis" ]]; then
    echo "ERROR - Missing \${pbench_run}/remotes.lis: '${pbench_run}/remotes.lis'" >&2
    exit 1
fi

# Register tools

printf -- "\nNow we'll register three tools that can be run in the Tool Meister containers,\n\n\t'vmstat', 'mpstat', and 'jaeger',\n\n... using a file containing all remote hosts running the Tool Meister.\n\n"

# Register the default tool set, will be recorded in
# ${pbench_run}/tools-v1-default
for tool in vmstat mpstat jaeger; do
    printf -- "\npbench-register-tool --name=${tool} --remotes=@${pbench_run}/remotes.lis\n"
    pbench-register-tool --name=${tool} --remotes=@${pbench_run}/remotes.lis
done

echo "sleep-iter-0 10" > ${pbench_run}/my-iterations.lis
echo "sleep-iter-11 11" >> ${pbench_run}/my-iterations.lis
echo "sleep-iter-42 12" >> ${pbench_run}/my-iterations.lis
echo "sleep-iter-42 120" >> ${pbench_run}/my-iterations.lis

set -x
pbench-user-benchmark --config="my-config-001" --iteration-list=${pbench_run}/my-iterations.lis --sysinfo=none -- sleep
set +x
