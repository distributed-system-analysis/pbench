# Ansible based installation

In the following, we describe how to install Pbench Agent` using an ansible playbook.

:::{note}
The same Pbench Agent version must be installed on all the test systems that participate in a benchmark run, there is no support for mixed installations.
:::

## Setup

1. Make sure that you have `ansible` package installed.

2. Install the `pbench.agent` ansible collection from Ansible Galaxy.

 ```console
 ansible-galaxy collection install pbench.agent
 ```

3. Tell ansible where to find these roles.

 ```console
 export ANSIBLE_ROLES_PATH=$HOME/.ansible/collections/ansible_collections/pbench/agent/roles:$ANSIBLE_ROLES_PATH
 ```

4. Create an inventory file (`~/.config/Inventory/myhosts.inv`) naming the hosts on which you wish to install pbench agent and including information about where the config file. Example inventory [file](assets/myhosts.inv).

5. Create a playbook [pbench_agent_install.yml](https://github.com/distributed-system-analysis/pbench/blob/main/agent/ansible/playbooks/pbench_agent_install.yml) file.

6. Run the playbook.

 ```console
 ansible-playbook -i ~/.config/Inventory/myhosts.inv pbench_agent_install.yml
 ```
