# containerized-pbench

## Openshift

We can either build an image using the following commands or pull the image from dockerhub

Build the image from source like

```
$ cd containerized-pbench/dockerfiles-pod
$ docker build -t pbench-agent .
```

Pull the image from dockerhub, if the image is not present on the openshift nodes, it is pulled automatically from dockerhub or registry

```
$ docker pull chaitanyaenr/pbench-agent
```

Run the following commands on openshift master

To launch a pbench-pod on all the nodes:
```
$ oc create -f containerized-pbench/openshift-templates/pbench-agent-daemonset.yml
```

By default pod is not scheduled on the master node since the scheduling is disabled. Since we are using daemonset, pods created by the Daemon controller have the machine already selected (.spec.nodeName is specified when the pod is created, so it is ignored by the scheduler) which means that the unschedulable field of a node is not respected by the DaemonSet controller and DaemonSet controller can make pods even when the scheduler has not been started. For this to work we have to create a service account and add it to the privileged scc like

```
$ oc create serviceaccount useroot
$ oc adm policy add-scc-to-user privileged -z useroot
$ oc patch daemonset pbench-agent --patch '{"spec":{"template":{"spec":{"serviceAccountName": "useroot"}}}}'
```

For pbench pod to run on the lb, we have configure it as a node ( node+lb ), disable scheduling on lb:

```
$ oadm manage-node node1.example.com --schedulable=false
```

Also make sure you label your nodes with type:pbench so that daemonset knows where to schedule the pbench-pod:

```
$ oc label node <node> type=pbench
```

## Jump node

### Build pbench-controller image 

```
$ cd containerized-pbench/dockerfiles-jump_node 
$ docker build -t pbench-controller .
```

### Run the container

Mount your ssh-keys, inventory to be used by pbench-ansible in to the container, /var on the host to /var/lib/pbench-agent on the container like 

```
$ docker run --privileged --net=host -v /path/to/keys:/root/.ssh -v /root/inventory:/root/inventory -v /var:/var/lib/pbench-agent pbench-controller
```

Make sure you set the pbench_server, benchmark and move_results variables in the vars file, the results are moved to the pbench server only when the move_results variable in the vars file is set to true. You can also set clear_results variable to true in case you want to clear off the existing results before starting a benchmark. A sample vars file is located at containerized-pbench/dockerfiles-jump_node/vars and it looks like
```
pbench_server=foo.example.com
clear_results=
benchmark=pbench-user-benchmark -- sleep 1
move_results=
```

Mount the vars file at /root/vars like
```
$ docker run --privileged --net=host -v /path/to/keys:/root/.ssh -v /root/inventory:/root/inventory -v /var/home:/var/lib/pbench-agent -v containerized-pbench/dockerfiles-jump_node/vars/:/root/vars pbench-controller
```
This will start a service which basically runs a script which sets up the pbench-agent config file and runs the benchmark.

Also make sure your ssh config file has Port set to 2202. There is a sample ssh config file for reference at containerized-pbench/dockerfiles-jump_node/config

## Need for privileged container
Docker needs to be run under privileged mode to get access to the host system's devices. Host's /var/lib/pbench-agent directory, /proc are mounted on to the container.
