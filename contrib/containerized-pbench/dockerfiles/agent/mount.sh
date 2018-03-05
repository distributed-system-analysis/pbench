#!/bin/bash

. /etc/profile.d/pbench-agent.sh
mkdir -p /var/lib/pbench-agent/tools-default
mount -o bind /proc_host /proc
while true; do sleep 1; done
