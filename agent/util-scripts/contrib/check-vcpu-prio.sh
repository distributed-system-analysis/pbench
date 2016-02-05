#!/bin/bash

vm=$1
for i in `virsh qemu-monitor-command --hmp $vm info cpus | sed 's/\r$//' | grep thread_id | awk -F"thread_id=" '{print $2}'`; do
	chrt -p  $i
done
