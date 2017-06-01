#!/bin/bash

. /etc/profile.d/pbench-agent.sh
mkdir -p /var/lib/pbench-agent/tools-default
cp /root/.ssh/id_rsa /opt/pbench-agent/id_rsa
sed -i "/^pbench_results_redirector/c pbench_results_redirector = ${pbench_server}" /opt/pbench-agent/config/pbench-agent.cfg
sed -i "/^pbench_web_server/c pbench_web_server = ${pbench_server}"  /opt/pbench-agent/config/pbench-agent.cfg
pbench-clear-tools
pbench-clear-results
ansible-playbook -i /root/inventory /root/pbench/contrib/ansible/openshift/pbench_register.yml
${benchmark}
pbench-move-results
while true; do sleep 1; done
