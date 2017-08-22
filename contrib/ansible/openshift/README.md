## Pbench Ansible
Playbook to register pbench tools on OpenShift cluster.

### Requirements
You need to have these installed
   - OpenShift
   - pbench

### Tools registered
master - sar, pidstat, iostat, oc, pprof, prometheus-metrics, disk, haproxy, perf

nodes - sar, pidstat, iostat, pprof, disk, perf

etcd - sar, pidstat, iostat, disk, perf

lb - sar, pidstat, iostat, disk, perf

glusterfs - sar, pidstat, iostat, pprof, disk, perf

### Sample inventory
Your inventory should have groups of hosts describing the roles they play in the OpenShift cluster. This playbook looks for the following groups in the inventory file:
```
[pbench-controller]

[masters]

[nodes]

[etcd]

[lb]

[glusterfs]

[pbench-controller:vars]
register_all_nodes=False
```

Note: glusterfs group represents cns nodes.
By default, tools registration is done on only two of the nodes, infra nodes. Setting the register_all_nodes to True will register tools on all of the nodes. 
Inventory file is copied on to the masters and pbench-controller. It will be available at /root/inv.

### Monitoring multiple endpoints using prometheus-metrics
By default the registered prometheus-metrics tool collects metrics from master's metrics endpoint, in case you want to monitor other endpoints, you need to add the endpoints under the [masters] group in the inventory as follows:
```
[masters]
<master> port=<port> cert=<cert> key=<key>
<endpoint> port=<port> cert=<cert> key=<key>
```

Note: if the port, cert and key are not defined, prometheus-metrics uses default values i.e  port=8443, cert=/etc/origin/master/admin.crt, key=/etc/origin/master/admin.key

### Accessing OpenShift Cluster
Kube config file is copied from the master node on to the pbench-controller. So you should be able to run oc commands and clusterloader from pbench-controller node.

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
