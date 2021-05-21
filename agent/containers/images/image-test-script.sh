#!/bin/bash

# A demonstration of how to use pbench-tool-meister-start with an existing
# Redis server and one or more remote hosts
export CONTROLLER=$(hostname -f)

DISTRO_DEFAULT="centos-8"
TAG_DEFAULT="a933ae45e"
REDIS_HOST_DEFAULT=$CONTROLLER
REDIS_PORT_DEFAULT=17001
PBENCH_RUN_DEFAULT=/var/tmp/test-run-dir

while :; do
    read -p "Specify distribution to test (or press 'ENTER' for default ${DISTRO_DEFAULT}): "
    DISTRO=${REPLY:-${DISTRO_DEFAULT}}
    read -p "Specify image tag to test (or press 'ENTER' for default ${TAG_DEFAULT}): "
    TAG=${REPLY:-${TAG_DEFAULT}}

    printf -- "Pulling tool-data-sink image to test...\n"
    if podman pull quay.io/pbench/pbench-agent-tool-data-sink-$DISTRO:$TAG ; then
        printf -- "Pull complete!\n\n"
        break
    else
        printf -- "Distro/tag combination could not be found, please try again.\n\n"
    fi
done

while :; do
    read -p "Specify redis host (or press 'ENTER' for default '$REDIS_HOST_DEFAULT'): "
    REDIS_HOST=${REPLY:-${REDIS_HOST_DEFAULT}}
    if ping -c 1 -W 1 ${REDIS_HOST} 2>&1 1>/dev/null ; then
        printf -- "Host pinged and validated!\n\n"
        break
    else
        printf -- "Host specified either does not exist or is unreachable, please try again:\n"
    fi
done

while :; do
    read -p "Specify Redis port (or press 'ENTER' for default port '${REDIS_PORT_DEFAULT}'): "
    let REDIS_PORT=${REPLY:-${REDIS_PORT_DEFAULT}}
    if ((1 <= $REDIS_PORT <= 65535)); then
        break
    else
        printf -- "Port must be a numeric value from 1 to 65535; please retry\n"
    fi
done

export REDIS_HOST REDIS_PORT
export PBENCH_REDIS_SERVER="${REDIS_HOST}:${REDIS_PORT}"

function wait_keypress {
    echo "Press any key to continue"
    while :; do
        read -t ${1} -n 1
        if [[ ${?} = 0 ]]; then
            return 0
        else
            echo "Waiting for a keypress"
        fi
    done
}

function yes_no_is_yes() {
    prompt=$1
    default=$2
    y_n=" (y/n)"
    read -N 1 -p "${prompt} ${y_n/${default}/[${default}]}: "
    printf -- "\n"
    lc_reply=$(tr '[:upper:]' '[:lower:]' <<< ${REPLY:-${default}})
    if [ "${lc_reply}" == "y" ]; then
        return 0
    fi
    return 1
}

clear

printf -- "We are now ready to begin the guided pbench image test process. \n\n\n"

wait_keypress 120

# The pbench_run directory is the path to the directory which is used as the
# persistent volume for the Tool Data Sink container, where the configuration
# as well as the collected data will be stored.

export pbench_run=$PBENCH_RUN_DEFAULT
while [[ -d $pbench_run ]]; do
    if yes_no_is_yes "Is it ok to delete the contents of '$pbench_run'?" "n"; then
        rm -rf ${pbench_run}
    else
        read -p "Suggest a new alternate directory for the pbench run (will be wiped/created): " pbench_run
    fi
done
export pbench_run
mkdir -p ${pbench_run}
printf -- "${pbench_run}\n" > ${pbench_run}/.path
export pbench_log=${pbench_run}/pbench.log

printf -- "\nThe benchmark run directory will be found inside:\n\n"

ls -ld ${pbench_run}
printf -- "\n"

wait_keypress 120


# Register tools

printf -- "\nNow, let's pick hosts to collect data from, as well as which tools we wish to register for that host.\n\n"

wait_keypress 120

while :; do
    read -p "Hostname (or press 'ENTER' for default '$CONTROLLER'): "
    hostvar=${REPLY:-${CONTROLLER}}
    if ping -c 1 -W 1 ${hostvar} 2>&1 1>/dev/null
    then
        echo $hostvar >> ${pbench_run}/remotes.lis
        if ! yes_no_is_yes "Another host?" "n"; then break; fi
    else
        printf -- "Host specified either does not exist or is unreachable, please try again:\n"
    fi
done
printf -- "\nDone selecting hosts:\n"
cat ${pbench_run}/remotes.lis
printf -- "\nNow to select data collection tools.\n\n"

# Registered tools will be recorded in ${pbench_run}/tools-v1-default
while :; do
    read -p "Tool name (type 'help' to see options): " tool
    if [ -z "$tool" ]
    then
        printf -- "Tool name empty. Please enter a tool name (at least one is required).\n"
    elif [ $tool == "help" ]
    then
        printf -- "\nAvailable tools:\n"
        pythonraw='
            import sys, json;
            meta = json.load(open(sys.argv[1]));
            print(
                " Transient:", *[f"\t{tool}" for tool in meta["transient"].keys()],
                " Persistent:", *[f"\t{tool}" for tool in meta["persistent"].keys()],
                sep="\n")'
        # Remove indentation because Python cares
        pythoncmd=$(sed -E -e 's/[[:space:]]{2,}//' <<<${pythonraw})
        python3 - /opt/pbench-agent/tool-scripts/meta.json <<<${pythoncmd}
    else
        cmd="pbench-register-tool --name=${tool} --remotes=@${pbench_run}/remotes.lis"
        printf -- "\n$cmd\n"
        $cmd
    fi
    if [ -d $pbench_run/tools-v1-default ]; then
        if ! yes_no_is_yes "Another tool?" "n"; then
            break
        fi
    fi
done
printf -- "\nDone registering tools. See selections below:\n\n"
ls -lR ${pbench_run}/tools-v1-default

printf -- "\n\n"
wait_keypress 120


# Start Tool Meister containers on remote host

printf -- "

Now please start the Tool Meister container on the specified host...
        $ podman run --name pbench-agent-tool-meister \\
                --network host --ulimit nofile=65536:65536 --rm -d \\
                -e REDIS_HOST=${REDIS_HOST} \\
                -e REDIS_PORT=${REDIS_PORT} \\
                -e PARAM_KEY=tm-default-\$(hostname -f) \\
                -e _PBENCH_TOOL_MEISTER_LOG_LEVEL=debug \\
                quay.io/pbench/pbench-agent-tool-meister-${DISTRO}:${TAG}

"

wait_keypress 120

printf -- "\n\nNow we will automatically start the local Tool Data Sink locally to pull tool data into our local volume.\n\n"

cmd="podman run --rm -d --name pbench-agent-tool-data-sink --network host
    --volume ${pbench_run}:/var/lib/pbench-agent:Z --ulimit nofile=65536:65536
    -e REDIS_HOST=${REDIS_HOST} -e REDIS_PORT=${REDIS_PORT}
    -e PARAM_KEY=tds-default -e _PBENCH_TOOL_DATA_SINK_LOG_LEVEL=debug
    quay.io/pbench/pbench-agent-tool-data-sink-${DISTRO}:${TAG}"
printf -- "\n$cmd\n"
$cmd

printf -- "\n
Optional: Now let's look at the 'podman logs' output from these containers;
        You will notice, if we did not start a Redis server yet,
        they'll just be waiting for it to show up.\n\n"

wait_keypress 120

printf -- "\n
Please start the Redis server on ${REDIS_HOST}:${REDIS_PORT} if not currently up

    $ podman run --name demo-tm-redis -p ${REDIS_PORT}:6379 --rm -d redis
    
    Note that the TDS and TMs notice the Redis server,
    but now wait for their 'PARAM_KEY' to show up.\n\n"

wait_keypress 120

source /etc/profile.d/pbench-agent.sh
source /opt/pbench-agent/base

group="default"

export script="demo"
export config="my-demo-config-000"
export benchmark_run_dir="${pbench_run}/${script}_${config}_${date_suffix}"
mkdir ${benchmark_run_dir}

printf -- "\n
Typically pbench-tool-meister-start is expecting a '\${benchmark_run_dir}' to store data
which is usually created by a pbench-user-benchmark and the like.
We mimic the same behavior with:

    benchmark_run_dir='${benchmark_run_dir}'\n\n"

wait_keypress 120

cat <<-__EOF__

Now we will begin with data collection, but before doing so, feel free to run this on any tool-meister hosts:

    $ podman run docker.io/alexeiled/stress-ng --cpu 4 --io 2 --timeout 300s --metrics-brief

This will serve as a sample workload to demonstrate meaningful data collection.
It runs for 300s by default, but feel free to alter that value (or ctrl-c for early graceful exit).

__EOF__

wait_keypress 120

# Start the Tool Meisters, collecting system information, and start any persistent tools.
cmd="_PBENCH_TOOL_MEISTER_START_LOG_LEVEL=debug pbench-tool-meister-start
    --orchestrate=existing 
    --redis-server=${REDIS_HOST}:${REDIS_PORT}
    --tool-data-sink=${CONTROLLER}
    --sysinfo=default ${group} 2>&1 | less -S"
printf -- "\n$cmd\n"
eval $cmd

printf -- "\n
The operation of pbench-tool-meister-start created the keys containing the
operational data for the Tool Data Sink and the Tool Meisters, then issued the
first 'sysinfo' collection, as requested, and sent the 'init' persistent tools
command.

At this point any registered persistent tools are up and running.
Next is the handling of transient tool start/stop.\n\n"
wait_keypress 120

# Option to start grafana, where it is listening on port 3000.
printf -- "\n
You can also now run a live metrics visualizer for the Prometheus & PCP data

    $ podman run --network host -d --rm --name pbench-viz quay.io/pbench/live-metric-visualizer
    
If done, open a browser to watch live metrics at: %s\n\n" "http://$(hostname -f):3000/"

wait_keypress 120

# start/stop/send tools

printf -- "\n\nNow we will start and stop two iterations of transient tool data collection.\n"

sample="sample42"
iterations="0-iter-zero 1-iter-one"

> ${benchmark_run_dir}/.iterations

for iteration in ${iterations}; do
    echo "${iteration}" >> ${benchmark_run_dir}/.iterations
    benchmark_results_dir="${benchmark_run_dir}/${iteration}/${sample}"
    mkdir -p ${benchmark_results_dir}

    printf -- "\n\nStarting iteration '${iteration}'; when we continue the transient tools will be started.\n\n"
    wait_keypress 120

    pbench-start-tools --group="${group}" --dir="${benchmark_results_dir}"

    printf -- "\n\nTransient tools have started for iteration '${iteration}'; when we continue they'll be stopped.\n\n"
    wait_keypress 120

    pbench-stop-tools --group="${group}" --dir="${benchmark_results_dir}"

    printf -- "\n\nTools have stopped for iteration '${iteration}'; each Tool Meister still has the data held locally.\n\n"
    wait_keypress 120
done

printf -- "\n
We have completed our two iterations, and next we'll loop through those
iterations requesting the tool data be sent back to the Tool Data Sink.\n\n"
wait_keypress 120

for iteration in ${iterations}; do
    benchmark_results_dir="${benchmark_run_dir}/${iteration}/${sample}"
    pbench-send-tools --group="${group}" --dir="${benchmark_results_dir}"
done

printf -- "\n
We have gathered the transient data from our two iterations, and
next we'll stop the Tool Meisters; this involves ending any persistent
tools, and gathering the final 'sysinfo' collection requested.\n\n"
wait_keypress 120

cmd="_PBENCH_TOOL_MEISTER_STOP_LOG_LEVEL=debug pbench-tool-meister-stop --sysinfo=default ${group}"
printf -- "\n$cmd\n"
eval $cmd

printf -- "\n
At this point the Tool Data Sink has stopped, along with the Tool
Meisters. The Redis server is still running, since the pbench-agent
CLI commands did not start it.  Next we dump the final directory
hierarchy of collected data to complete the test.\n\n"
wait_keypress 120

# Dump our local environment
find ${pbench_run} -ls | less -S

wait_keypress 120

if [ "$(podman ps | grep pbench-viz)" ]; then
    if yes_no_is_yes "Would you like the live-metric-visualizer to be terminated?" "n"
    then
        cmd="podman kill pbench-viz"
        printf -- "Running: $cmd\n"
        $cmd
    fi
fi

if [ "$(podman ps | grep demo-tm-redis)" ]; then
    if yes_no_is_yes "Would you like the redis container to be terminated?" "n"
    then
        cmd="podman kill demo-tm-redis"
        printf -- "Running: $cmd\n"
        $cmd
    fi
fi

printf -- "\nCongratulations, you've completed the full benchmarking process!\n"
