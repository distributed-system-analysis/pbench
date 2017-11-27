#!/bin/bash

. /etc/profile.d/pbench-agent.sh
mkdir -p /var/lib/pbench-agent/tools-default
cp /root/.ssh/id_rsa /opt/pbench-agent/id_rsa

# Set pbench-server in the config
sed -i "/^pbench_results_redirector/c pbench_results_redirector = ${pbench_server}" /opt/pbench-agent/config/pbench-agent.cfg
sed -i "/^pbench_web_server/c pbench_web_server = ${pbench_server}"  /opt/pbench-agent/config/pbench-agent.cfg

# Clear tools
pbench-clear-tools

# Register tools
ansible-playbook -i /root/inventory /root/pbench/contrib/ansible/openshift/pbench_register.yml

if [[ "$?" == 0 ]]; then
        echo -e "-----------------------------------------------------------\n\n\n"
        echo -e "		PBENCH TOOLS REGISTERED SUCCESSFULLY		\n\n\n"
        echo "-----------------------------------------------------------"
else
        echo -e "-----------------------------------------------------------\n\n\n"
        echo -e "		PBENCH REGISTRATION FAILED		\n\n\n"
        echo "-----------------------------------------------------------"
fi

if [[ "${clear_results}" == "true" ]] || [[ "${clear_results}" == "True" ]]; then
       pbench-clear-results
fi       

# Run the benchmark
${benchmark}
benchmark_status=$?

if [[ "${move_results}" == "true" ]] || [[ "${move_results}" == "True" ]]; then
        pbench-move-results
fi

if [[ "$benchmark_status" == 0 ]]; then
	echo -e "-----------------------------------------------------------\n\n\n"
	echo -e "		OCP SCALE TEST COMPLETED		\n\n\n"
	echo "-----------------------------------------------------------"
else
	echo -e "-----------------------------------------------------------\n\n\n"
	echo -e "		OCP SCALE TEST FAILED		\n\n\n"
	echo "-----------------------------------------------------------"
fi
