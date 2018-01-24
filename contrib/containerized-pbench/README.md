## Containerized pbench
This directory contains OpenShift templates, dockerfiles needed to build and run containerized pbench.

### Prepare the nodes you want to monitor
The nodes need to have pbench-agent images on it. In case the nodes do not have the images, please pull them from dockerhub:

#### pbench-agent
```
$ docker pull ravielluri/image:agent
$ docker tag ravielluri/image:agent pbench-agent:latest
```

### Label the nodes with a type=pbench label
```   
$ oc label node <node> type=pbench
```

### Create a pbench namespace
```   
$ oc create -f pbench/contrib/containerized-pbench/openshift-templates/pbench-namespace.yml
```

### Create a service account and add it to the privileged Security Context Constraints
```
$ oc create serviceaccount useroot
$ oc adm policy add-scc-to-user privileged -z useroot
```

### Create pbench-agent pods and patch the daemonset
```
$ oc create -f pbench/contrib/containerized-pbench/openshift-templates/pbench-agent-daemonset.yml
$ oc patch daemonset pbench-agent --patch \ '{"spec":{"template":{"spec":{"serviceAccountName": "useroot"}}}}'
```

## Prepare the jump host to run pbench-controller

### Get the controller image from dockerhub
```
$ docker pull ravielluri/image:controller
$ docker tag ravielluri/image:controller pbench-controller:latest
```

### keys
copy the ssh keys to /root/scale-testing/keys. The keys directory should contain a perf key named as id_rsa_perf,  id_rsa - the private key needed to copy the results to the pbench server, authorized_keys file -ansible needs to have a passwordless authentication to localhost inside the container, ssh config which looks like:
```
Host *
	User root
        Port 2022
        StrictHostKeyChecking no
        PasswordAuthentication no
        UserKnownHostsFile ~/.ssh/known_hosts
        IdentityFile ~/.ssh/id_rsa_perf  
      
Host *pbench-server
        User root
        Port 22
        StrictHostKeyChecking no
        PasswordAuthentication no
        UserKnownHostsFile ~/.ssh/known_hosts
        IdentityFile /opt/pbench-agent/id_rsa
```

### Inventory
Make sure you have the inventory used to install openshift and it should look like:
```
[pbench-controller]

[masters]
    
[nodes]

[etcd]

[lb]

[prometheus-metrics]
<host> port=8443 cert=/etc/origin/master/admin.crt key=/etc/origin/master/admin.key
<host> port=10250 cert=/etc/origin/master/admin.crt key=/etc/origin/master/admin.key

[pbench-controller:vars]
register_all_nodes=False
```

Set register_all_nodes to true if the tools needs to be registered on all the nodes, if not set to true, it registers pbench tools on just two of the nodes.

NOTE: 
- Make sure all the variables are defined under [group:vars], all the stuff under [groups] are assumed to be the node ip’s.

- In HA environment, we will have an lb which is not an openshift node. This means that there won’t be a pbench-agent pod running on the lb, pbench-ansible will fail registering tools as it won’t find a pbench-agent pod. So, we need to make a copy of the original inventory and get rid of the lb node from the inventory which is being mounted into the container.
  
- We need to make sure we stick to either ip’s or hostnames in both inventory and openshift for certificates to be valid.

## Run benchmarks
Edit the vars file and set benchmark_type variable to the benchmark that you want to run, pbench_server - host where the results are moved when move_results is set to True.

### Avalaible benchmark_type options:
- nodeVertical
- http
- masterVertical

## Run
```
$ docker_id=$(docker run -t -d --name=controller --net=host --privileged \
  -v /var/lib/pbench-agent:/var/lib/pbench-agent \
  -v <path to results directory>:/var/lib/pbench-agent \
  -v <path to the inventory>:/root/inventory \
  -v <path to the vars file>:/root/vars \
  -v <path to the keys>:/root/.ssh \
  -v <path to benchmark.sh>:/root/benchmark.sh pbench-controller
```

### Results
If move_results is set, the results are moved to the pbench server. In case you want to look at the results before moving, set move_results to False and the results will be available in the mounted directory.

### Monitoring the benchmark
In case you want to monitor what's going on inside the container, please take a look at the logs:

```
$ docker logs -f pbench-controller
```
You should be able to see the pbench-ansible registering the tools and the benchmark stdout.

### Need for privileged container
Docker needs to be run under privileged mode to get access to the host system's devices. Host's /var/lib/pbench-agent directory, /proc are mounted on to the container.
