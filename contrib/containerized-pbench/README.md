# Running a Pbench Agent-driven Workload in a Container

The Pbench Agent is available for use in a zero-installation scenario
via containerized execution.  Agent containers are available from
[quay.io/pbench](https://quay.io/organization/pbench):  there's a
repository for each distribution (e.g.,
[pbench-agent-all-centos-9](https://quay.io/repository/pbench/pbench-agent-all-centos-9?tab=tags))
with tags for each Agent release as well as for "hot builds" for
each development branch.

The `pbench` script provided here is a wrapper which facilitates
the invocation of a Pbench Agent command using a containerized
deployment of the Pbench Agent.  Simply prefix a Pbench Agent
command line with the path to this script to run it inside a
container, without needing to install the Agent on the host
system. (This is easily done by defining a shell alias for it.)

The provided `pbench_demo` script shows the sequence of commands
which might be used to perform a `fio` benchmark run.