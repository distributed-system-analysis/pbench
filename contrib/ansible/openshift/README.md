## Pbench Ansible
Playbook to register pbench tools on openshift cluster.

### Requirements
You need to have these installed
   - Openshift
   - pbench

### Tools registered
master - sar, pidstat, iostat, oc, pprof

nodes - sar, pidstat, iostat, pprof

etcd - sar, pidstat, iostat

lb - sar, pidstat, iostat

### Sample inventory
Your inventory should have groups of hosts describing the roles they play in the openshift cluster. This playbook looks for the following groups in the inventory file:

[pbench-controller]

[masters]

[nodes]

[etcd]

[lb]

[pbench-controller:vars]
register_all_nodes=False

By default, tools registration is done on only two of the nodes, setting the register_all_nodes to True will register tools on all of the nodes.

### Run
Currently pbench is run under the root user, so the playbook also needs to run as root.
```
$ ansible-playbook -i /path/to/inventory --extra-vars '{ "ansible_ssh_private_key_file":"" }' pbench_register.yml
```
By default the interval for ose_master_interval, ose_node_interval and default_tools_interval are set to 10 seconds.

You can override the variables like
```
$ ansible-playbook -i /path/to/inventory --extra-vars '{"default_tools_interval":"30"}' pbench_register.yml
```
### Labeling of nodes
Each node has a label, <index> associated with it. Masters are labeled with svt_master_<index>, so for the first master, the label looks like svt_master_1. Similarly nodes are labeled with svt_node_<index>, etcd with svt_etcd_<index> and lb with svt_lb_<index>. If the nodes in groups are same, for example if first master and second etcd nodes are same then the label looks like svt_master_1_etcd_2.
