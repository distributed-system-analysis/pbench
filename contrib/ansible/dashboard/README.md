## Ansible playbook for pbench dashboard
This will ease installation, using pbench dashboard.

## Required
- Ansible needs to be installed on the host where you want to run this playbook
- Python
- JSON file containing the following key values: "elasticsearch", "production", "run_index", "prefix"

## Run
Running the below command from the root directory of the dashboard will install pbench dashboard, on the hosts mentioned under [servers:children] in the inventory file. 
There's also an option to define the dashboard configuration  in the inventory file. 
```
$ ansible-playbook -i inventory dashboard-install.yml
$ ansible-playbook -i inventory dashboard-deploy.yml
```
