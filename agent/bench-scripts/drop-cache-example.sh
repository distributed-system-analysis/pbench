#!/bin/bash -x
# drop-cache.sh - an example of a pbench-fio cache-dropping script
# here is an example cache dropping script for Ceph cluster
# it assumes that there is a ceph-ansible inventory file in /root/ansible-hosts
# containing a [osds] host group and a list of Ceph OSD hosts underneath
# the script must be set to be executable using a command like
#   chmod 755 drop-cache.sh

ansible -m shell -f 12 -i /root/ansible-hosts -a "sync ; echo 3 > /proc/sys/vm/drop_caches" osds
