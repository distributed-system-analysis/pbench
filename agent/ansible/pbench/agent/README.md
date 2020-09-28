# Ansible Collection - pbench.agent

The roles in this collection allow the installation of the pbench-agent RPM and related RPMs, and the configuration of the agent for use in a particular environment.

More information about pbench can be found at https://github.com/distributed-system-analysis/pbench.

The roles assume that the following variables are defined:

- pbench_repo_url_prefix: the repo where the RPMs can be found (default: https://copr-be.cloud.fedoraproject.org/results/ndokos).
- pbench_config_url: the location where one or more config files can be obtained (default: none).
- pbench_config_dest: the location within the pbench-agent installation directory where the config file is going to be copied (default: /opt/pbench-agent/config/)
- pbench_config_files: a list of config files to be installed on an agent (default: '["pbench-agent.cfg"]').
- pbench_key_url: the location where an ssh key can be obtained for sending results to a server (default: none).
- pbench_key_dest: the location within the pbench-agent installation directory where the key is going to be copied. (default: /opt/pbench-agent/).

Some of these are defaulted for convenience, but pbench_repo_url_prefix and pbench_key_url are specific to an environment and need to be specified locally (most likely in the inventory file).

An example playbook can be obtained from

    https://github.com/distributed-system-analysis/pbench/blob/master/agent/ansible/pbench_agent_install.yml

or you can use the raw link to wget/curl the file:

    https://raw.githubusercontent.com/distributed-system-analysis/pbench/master/agent/ansible/pbench_agent_install.yml

An example inventory file that can be edited to suit your circumstances can be obtained from 

    https://github.com/distributed-system-analysis/pbench/blob/master/agent/ansible/Inventory/pbench_agent.hosts.example

The raw link for that is

    https://raw.githubusercontent.com/distributed-system-analysis/pbench/master/agent/ansible/Inventory/pbench_agent.hosts.example
