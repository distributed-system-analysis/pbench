## Ansible playbooks for installing and deploying the pbench dashboard
This will ease installation, and deployment of the pbench dashboard.

## Required
- Ansible needs to be installed on the host where you want to run this playbook
- An inventory file containing the following key values defined:
  - "`elasticsearch`", "`production`", "`run_index`", "`prefix`", "`graphql`"
    See the `/web-server/v0.4/README.md` for more details. 

## Run
Running the below commands from this checked-out directory to install the
pbench dashboard components locally, and then deploy hosts mentioned under
the "`[servers:children]`" section of the given `inventory` file.
 
There's also an option to define the dashboard configuration in the provided
inventory file.

See the `inventory` file in this directory for an example.
```
$ # First add a link to the "dist" folder where the dashboard will be built.
$ ln -sf ../../../web-server/v0.4/dist dist
$ ansible-playbook -i inventory dashboard-install.yml
$ ansible-playbook -i inventory dashboard-deploy.yml
```
