## Pbench Ansible
Playbook to register pbench tools on OpenShift cluster.

### Requirements
You need to have these installed
   - OpenShift
   - pbench

### Tools registered
master - sar, pidstat, iostat, oc, pprof, prometheus-metrics, disk, haproxy, perf

nodes - sar, pidstat, iostat, disk, perf

etcd - sar, pidstat, iostat, disk, perf

lb - sar, pidstat, iostat, disk, perf

glusterfs - sar, pidstat, iostat, disk, perf

infra - sar, pidstat, iostat, disk, perf

### Sample inventory
Your inventory should have groups of hosts describing the roles they play in the OpenShift cluster. This playbook looks for the following groups in the inventory file:
```
[pbench-controller]

[masters]

[nodes]

[etcd]

[lb]

[glusterfs]

[infra]

[pprof]

[prometheus-metrics]
<host> port=8443 cert=<cert> key=<key>
<host> port=10250 cert=/etc/origin/master/admin.crt key=/etc/origin/master/admin.key

[pbench-controller:vars]
register_all_nodes=False
```

Note: glusterfs group represents cns nodes.
By default, tools registration is done on only two of the nodes, infra nodes. Setting the register_all_nodes to True will register tools on all of the nodes.
Inventory file is copied on to the masters and pbench-controller. It will be available at /root/inv.

By default we register only the masters for pprof, in order to monitor other nodes they need to be added to the [pprof] group.

### Monitoring multiple endpoints using prometheus-metrics
prometheus-metrics tool is registered on the first master, the endpoints to be monitored should be added under the [prometheus-metrics] group in the inventory file as follows:
```
[prometheus-metrics]
<master> port=<port> cert=<cert> key=<key>
<endpoint> port=<port> cert=<cert> key=<key>
```

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
