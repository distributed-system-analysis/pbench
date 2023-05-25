# Pbench Agent Container

Pbench Agent is available as container images on [Quay.io](https://quay.io/organization/pbench). This makes pbench-agent a distro-independent solution and it could also be used in any containerized ecosystem.

**Want to build container images from sources?**  
Follow [README](https://github.com/distributed-system-analysis/pbench/blob/main/agent/containers/images/README.md)

Running Pbench Agent container is as simple as  
```console
podman run quay.io/pbench/pbench-agent-all-centos-8
```  
Depending on the use cases one has to run these containers with privileged mode, host network, pid, ipc, mount required volumes, etc.

Example:
```console
podman run --name pbench --rm -ti --privileged --ipc=host --net=host --pid=host -e HOST=/host -e NAME=pbench -e IMAGE=quay.io/pbench/pbench-agent-all-centos-8 -v /run:/run -v /var/log:/var/log -v /etc/machine-id:/etc/machine-id -v /etc/localtime:/etc/localtime -v /:/host quay.io/pbench/pbench-agent-all-centos-8
```

:::{note}
The volumes and config shown in the command snippet above may vary depending on users needs.
:::

Possibilities are endless, please give it a try <https://quay.io/organization/pbench>.
