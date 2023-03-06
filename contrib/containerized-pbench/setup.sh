#!/bin/bash

if [[ -z "${1}" ]]; then
    echo "Please provide a target Pbench Server (<host name>:<port number>) to move the results to as the first argument." >&2
    exit 2
fi
cat > ./pbench-agent.cfg.tmp <<- EOF
	[DEFAULT]
	pbench_install_dir = /opt/pbench-agent
	pbench_web_server = ${1}
	[config]
	path = %(pbench_install_dir)s/config
	files = pbench-agent-default.cfg
	EOF

# Create a directory to use as the `/var/lib/pbench-agent` directory mounted
# in the container.
mkdir -p var_lib_pbench-agent

podman run \
    -it \
    --rm \
    --network host \
    -v ./gen-token.sh:/gen-token.sh:z \
    -v ./pbench-agent.cfg.tmp:/opt/pbench-agent/config/pbench-agent.cfg:z \
    -v ./var_lib_pbench-agent:/var/lib/pbench-agent:z \
    quay.io/pbench/pbench-agent-all-centos-8:latest /gen-token.sh
