# Ansible based installation

In the following, we describe how to install `pbench-agent` using an ansible playbook.

:::{note}
The same pbench-agent version must be installed on all the test systems that participate in a benchmark run, there is no support for mixed installations.
:::

## Setup

1. Make sure that you have ansible and ansible-galaxy installed on your laptop (or wherever you decide to run the playbooks).

 ```console
 dnf install ansible
 ```

2. Install the ansible roles from Ansible Galaxy.

 ```console
 ansible-galaxy collection install pbench.agent
 ```

3. Tell ansible where to find these roles.

 ```console
 export ANSIBLE_ROLES_PATH=$HOME/.ansible/collections/ansible_collections/pbench/agent/roles:$ANSIBLE_ROLES_PATH
 ```

4. Create an inventory file (`~/.config/Inventory/myhosts.inv`) naming the hosts on which you wish to install pbench-agent and including information about where the config file and ssh key file can be found. Example inventory [file](assets/myhosts.inv).

5. Create a playbook [file](assets/pbench_agent_install.yml)

6. Run the playbook.

 ```console
 ansible-playbook -i ~/.config/Inventory/myhosts.inv pbench_agent_install.yml
 ```
